import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from ..database import get_db, Application, User, License, AppVariable, AppFile, AuditLog, Developer, SubscriptionTier, Blacklist, Reseller, PlanKey
from ..security import decode_access_token, generate_random_token, generate_license_key, hash_password
from ..config import log_audit, send_discord_webhook
from .auth_api import get_current_developer

router = APIRouter(prefix="/api/v1/admin", tags=["Developer Admin API"])

# ==================== Pydantic Schemas ====================
class CreateAppRequest(BaseModel):
    name: str
    version: Optional[str] = "1.0"
    hwid_lock_enabled: Optional[bool] = True
    vpn_block_enabled: Optional[bool] = False
    session_timeout_minutes: Optional[int] = 60
    download_link: Optional[str] = ""
    custom_message: Optional[str] = ""
    webhook_url: Optional[str] = ""

class UpdateAppRequest(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    status: Optional[str] = None
    hwid_lock_enabled: Optional[bool] = None
    vpn_block_enabled: Optional[bool] = None
    session_timeout_minutes: Optional[int] = None
    download_link: Optional[str] = None
    custom_message: Optional[str] = None
    webhook_url: Optional[str] = None

class CreateLicenseRequest(BaseModel):
    app_id: int
    count: int = 1
    duration_days: int = 30
    level: str = "default"
    level_rank: int = 1
    mask: str = "JOYST-XXXX-XXXX-XXXX"
    notes: Optional[str] = ""

class CreateUserManualRequest(BaseModel):
    app_id: int
    username: str
    password: str
    duration_days: int = 30 # -1 for Lifetime
    subscription_tier: str = "default"
    level: int = 1
    hwid: Optional[str] = None

class BanUserRequest(BaseModel):
    reason: Optional[str] = "Violation of terms"

class ExtendUserRequest(BaseModel):
    days: int = 30

class BulkDeleteUsersRequest(BaseModel):
    user_ids: List[int]

class PurgeExpiredUsersRequest(BaseModel):
    app_id: int

class ResetAllHwidRequest(BaseModel):
    app_id: int

class BulkExtendUsersRequest(BaseModel):
    app_id: int
    user_ids: Optional[List[int]] = None
    days: int = 7

class BulkBanUsersRequest(BaseModel):
    user_ids: List[int]
    reason: Optional[str] = "Bulk banned by Admin"

class CreateVariableRequest(BaseModel):
    app_id: int
    name: str
    value: str
    is_encrypted: bool = True

class CreateTierRequest(BaseModel):
    app_id: int
    name: str
    level_rank: int = 1
    description: Optional[str] = ""

class CreateFileRequest(BaseModel):
    app_id: int
    file_id: str
    file_name: str
    file_url: str
    file_size: Optional[int] = 0

class CreateBlacklistRequest(BaseModel):
    app_id: int
    type: str # ip, hwid
    data: str
    reason: Optional[str] = "Blacklisted by Admin"

class CreateResellerRequest(BaseModel):
    username: str
    password: str
    balance: int = 100
    allowed_apps: Optional[str] = "all"

class UpdateResellerCreditsRequest(BaseModel):
    amount: int
    operation: Optional[str] = "add"

class ResetResellerPasswordRequest(BaseModel):
    new_password: str

class UpdateResellerAppsRequest(BaseModel):
    allowed_apps: str

class PlanUpgradeRequest(BaseModel):
    plan_name: str # Developer, Enterprise

class TestWebhookRequest(BaseModel):
    app_id: int
    custom_message: str

# ==================== 1. APPLICATIONS ====================
@router.get("/apps")
async def list_apps(dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    result = []
    for app in apps:
        user_count = db.query(User).filter(User.app_id == app.id).count()
        license_count = db.query(License).filter(License.app_id == app.id).count()
        active_licenses = db.query(License).filter(License.app_id == app.id, License.status == "unused").count()
        file_count = db.query(AppFile).filter(AppFile.app_id == app.id).count()
        var_count = db.query(AppVariable).filter(AppVariable.app_id == app.id).count()
        result.append({
            "id": app.id,
            "name": app.name,
            "owner_id": app.owner_id,
            "secret": app.secret,
            "version": app.version,
            "status": app.status,
            "hwid_lock_enabled": app.hwid_lock_enabled,
            "vpn_block_enabled": app.vpn_block_enabled,
            "session_timeout_minutes": app.session_timeout_minutes,
            "download_link": app.download_link,
            "custom_message": app.custom_message,
            "webhook_url": app.webhook_url,
            "created_at": app.created_at.isoformat(),
            "stats": {
                "total_users": user_count,
                "total_licenses": license_count,
                "unused_licenses": active_licenses,
                "total_files": file_count,
                "total_vars": var_count
            }
        })
    return {"success": True, "owner_id": dev.owner_id, "apps": result}

@router.post("/apps")
async def create_app(data: CreateAppRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app_name = data.name.strip()
    if not app_name:
        raise HTTPException(status_code=400, detail="Application name is required")
    
    # Check duplicate application name under same developer workspace
    existing_app = db.query(Application).filter(Application.developer_id == dev.id, Application.name == app_name).first()
    if existing_app:
        raise HTTPException(status_code=400, detail=f"An application named '{app_name}' already exists in your workspace. Please choose a unique name.")

    # Check developer plan limits
    app_count = db.query(Application).filter(Application.developer_id == dev.id).count()
    if app_count >= dev.max_apps:
        raise HTTPException(status_code=400, detail=f"Your {dev.plan} plan limit reached ({dev.max_apps} apps max). Please upgrade to Enterprise.")

    from ..config import DEFAULT_DISCORD_WEBHOOK_URL
    app_secret = "sec_" + generate_random_token(32)
    new_app = Application(
        developer_id=dev.id,
        name=app_name,
        owner_id=dev.owner_id,
        secret=app_secret,
        version=data.version or "1.0",
        status="enabled",
        hwid_lock_enabled=data.hwid_lock_enabled,
        vpn_block_enabled=data.vpn_block_enabled,
        session_timeout_minutes=data.session_timeout_minutes or 60,
        download_link=data.download_link or "",
        custom_message=data.custom_message or "",
        webhook_url=data.webhook_url or DEFAULT_DISCORD_WEBHOOK_URL
    )
    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    # Seed default tier
    default_tier = SubscriptionTier(app_id=new_app.id, name="default", level_rank=1, description="Standard Access")
    vip_tier = SubscriptionTier(app_id=new_app.id, name="VIP", level_rank=2, description="Premium Access")
    db.add_all([default_tier, vip_tier])
    db.commit()

    log_audit(db, new_app.id, "APP_CREATED", details=f"New application '{new_app.name}' initialized with Joyst Auth", status="SUCCESS")

    return {"success": True, "message": "Application created successfully", "app": {
        "id": new_app.id,
        "name": new_app.name,
        "owner_id": new_app.owner_id,
        "secret": new_app.secret,
        "version": new_app.version,
        "status": new_app.status
    }}

@router.put("/apps/{app_id}")
async def update_app(app_id: int, data: UpdateAppRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if data.name is not None:
        app.name = data.name.strip()
    if data.version is not None:
        app.version = data.version
    if data.status is not None:
        app.status = data.status
    if data.hwid_lock_enabled is not None:
        app.hwid_lock_enabled = data.hwid_lock_enabled
    if data.vpn_block_enabled is not None:
        app.vpn_block_enabled = data.vpn_block_enabled
    if data.session_timeout_minutes is not None:
        app.session_timeout_minutes = data.session_timeout_minutes
    if data.download_link is not None:
        app.download_link = data.download_link
    if data.custom_message is not None:
        app.custom_message = data.custom_message
    if data.webhook_url is not None:
        app.webhook_url = data.webhook_url
    
    db.commit()
    return {"success": True, "message": "Application updated successfully"}

@router.post("/apps/{app_id}/regenerate-secret")
async def regenerate_app_secret(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    app.secret = "sec_" + generate_random_token(32)
    db.commit()
    return {"success": True, "message": "App Secret regenerated successfully", "new_secret": app.secret}

@router.delete("/apps/{app_id}")
async def delete_app(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    db.delete(app)
    db.commit()
    return {"success": True, "message": "Application and all associated data deleted"}

# ==================== 2. LICENSES ====================
@router.get("/licenses")
async def list_licenses(
    app_id: int,
    status: Optional[str] = None,
    search: Optional[str] = None,
    dev: Developer = Depends(get_current_developer),
    db: Session = Depends(get_db)
):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "licenses": []}

    query = db.query(License).filter(License.app_id == app_id)
    if status:
        query = query.filter(License.status == status)
    if search:
        query = query.filter(
            (License.license_key.contains(search)) |
            (License.used_by_username.contains(search)) |
            (License.notes.contains(search))
        )
    
    licenses = query.order_by(desc(License.id)).limit(500).all()
    return {
        "success": True,
        "licenses": [
            {
                "id": lic.id,
                "app_id": lic.app_id,
                "key": lic.license_key,
                "duration_days": lic.duration_days,
                "level": lic.level,
                "level_rank": lic.level_rank,
                "status": lic.status,
                "used_by": lic.used_by_username,
                "used_at": lic.used_at.isoformat() if lic.used_at else None,
                "created_at": lic.created_at.isoformat(),
                "notes": lic.notes
            }
            for lic in licenses
        ]
    }

@router.post("/licenses")
async def generate_licenses(
    data: CreateLicenseRequest,
    authorization: Optional[str] = Header(None),
    dev: Developer = Depends(get_current_developer),
    db: Session = Depends(get_db)
):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    count = min(max(1, data.count), 500)

    # Check if caller is a Reseller
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    payload = decode_access_token(token) if token else {}
    if payload.get("role") == "reseller":
        reseller_id = payload.get("reseller_id")
        reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
        if not reseller:
            raise HTTPException(status_code=401, detail="Reseller account not found")
        if reseller.balance < count:
            raise HTTPException(status_code=400, detail=f"Insufficient balance! You have {reseller.balance} credits remaining, but requested {count} keys.")
        reseller.balance -= count

    created_keys = []
    mask = data.mask or "JOYST-XXXX-XXXX-XXXX"

    for _ in range(count):
        raw_key = generate_license_key(mask)
        while db.query(License).filter(License.license_key == raw_key).first():
            raw_key = generate_license_key(mask)
        
        lic = License(
            app_id=data.app_id,
            license_key=raw_key,
            duration_days=data.duration_days,
            level=data.level or "default",
            level_rank=data.level_rank or 1,
            status="unused",
            notes=data.notes or "",
            created_at=datetime.datetime.utcnow()
        )
        db.add(lic)
        created_keys.append(raw_key)
    
    db.commit()
    log_audit(db, app.id, "GENERATE_KEYS", details=f"Generated {count} keys ({data.level}, {data.duration_days} days)", status="SUCCESS")

    return {
        "success": True,
        "message": f"Successfully generated {count} license key(s)",
        "keys": created_keys
    }

@router.delete("/licenses/{license_id}")
async def delete_license(license_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    lic = db.query(License).join(Application).filter(
        License.id == license_id,
        Application.developer_id == dev.id
    ).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    db.delete(lic)
    db.commit()
    return {"success": True, "message": "License deleted successfully"}

@router.post("/licenses/bulk-delete")
async def bulk_delete_licenses(app_id: int, delete_type: str, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if delete_type == "unused":
        deleted = db.query(License).filter(License.app_id == app_id, License.status == "unused").delete()
    elif delete_type == "used":
        deleted = db.query(License).filter(License.app_id == app_id, License.status == "used").delete()
    elif delete_type == "all":
        deleted = db.query(License).filter(License.app_id == app_id).delete()
    else:
        raise HTTPException(status_code=400, detail="Invalid delete type")
    
    db.commit()
    return {"success": True, "message": f"Deleted {deleted} license(s)"}

@router.post("/licenses/{license_id}/toggle-pause")
async def toggle_license_pause(license_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    lic = db.query(License).join(Application).filter(
        License.id == license_id,
        Application.developer_id == dev.id
    ).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found")
    
    if lic.status == "paused":
        lic.status = "unused" if not lic.used_by_username else "used"
    else:
        lic.status = "paused"
    
    db.commit()
    return {"success": True, "message": f"License status updated to {lic.status}", "new_status": lic.status}

# ==================== 3. USERS & HWID ====================
@router.get("/users")
async def list_users(
    app_id: int,
    search: Optional[str] = None,
    dev: Developer = Depends(get_current_developer),
    db: Session = Depends(get_db)
):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "users": []}

    query = db.query(User).filter(User.app_id == app_id)
    if search:
        query = query.filter(
            (User.username.contains(search)) |
            (User.last_ip.contains(search)) |
            (User.hwid.contains(search)) |
            (User.key_used.contains(search))
        )
    
    users = query.order_by(desc(User.last_login)).limit(500).all()
    result = []
    for u in users:
        is_expired = u.expires_at and datetime.datetime.utcnow() > u.expires_at
        time_left_str = "Lifetime"
        if u.expires_at:
            if is_expired:
                time_left_str = "Expired"
            else:
                diff = u.expires_at - datetime.datetime.utcnow()
                time_left_str = f"{diff.days}d {diff.seconds // 3600}h"

        result.append({
            "id": u.id,
            "app_id": u.app_id,
            "app_name": app.name,
            "username": u.username,
            "hwid": u.hwid,
            "hwid_lock_override": u.hwid_lock_override,
            "last_ip": u.last_ip,
            "registered_ip": u.registered_ip,
            "subscription": u.subscription_tier,
            "level": u.level,
            "expires_at": u.expires_at.isoformat() if u.expires_at else "Lifetime",
            "time_left": time_left_str,
            "is_expired": is_expired,
            "is_banned": u.is_banned,
            "ban_reason": u.ban_reason,
            "key_used": u.key_used,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat()
        })
    return {"success": True, "users": result}

@router.post("/users/manual-create")
async def create_user_manual(data: CreateUserManualRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    existing = db.query(User).filter(User.app_id == data.app_id, User.username == data.username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this username already exists in this app")
    
    expires_at = None
    if data.duration_days != -1 and data.duration_days < 90000:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=data.duration_days)

    new_user = User(
        app_id=data.app_id,
        username=data.username.strip(),
        password_hash=hash_password(data.password),
        subscription_tier=data.subscription_tier or "default",
        level=data.level or 1,
        expires_at=expires_at,
        hwid=data.hwid.strip() if data.hwid else None,
        registered_ip="Manual Entry",
        key_used="Manual by Developer"
    )
    db.add(new_user)
    db.commit()
    log_audit(db, app.id, "MANUAL_USER_CREATE", username=new_user.username, details="Created manually by developer", status="SUCCESS")
    return {"success": True, "message": f"User '{new_user.username}' created successfully"}

@router.post("/users/{user_id}/reset-hwid")
async def reset_user_hwid(user_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    user = db.query(User).join(Application).filter(
        User.id == user_id,
        Application.developer_id == dev.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.hwid = None
    db.commit()
    log_audit(db, user.app_id, "RESET_HWID", username=user.username, details="HWID reset by developer", status="SUCCESS")
    return {"success": True, "message": f"HWID for user '{user.username}' reset successfully."}

@router.post("/users/{user_id}/toggle-ban")
async def toggle_ban_user(user_id: int, data: BanUserRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    user = db.query(User).join(Application).filter(
        User.id == user_id,
        Application.developer_id == dev.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_banned = not user.is_banned
    if user.is_banned:
        user.ban_reason = data.reason or "Banned by developer"
        log_audit(db, user.app_id, "BAN_USER", username=user.username, details=f"Banned: {user.ban_reason}", status="DANGER")
    else:
        user.ban_reason = ""
        log_audit(db, user.app_id, "UNBAN_USER", username=user.username, details="Unbanned by developer", status="SUCCESS")
    
    db.commit()
    return {"success": True, "message": f"User '{user.username}' is now {'banned' if user.is_banned else 'active'}", "is_banned": user.is_banned}

@router.post("/users/{user_id}/extend")
async def extend_user_subscription(user_id: int, data: ExtendUserRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    user = db.query(User).join(Application).filter(
        User.id == user_id,
        Application.developer_id == dev.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.expires_at is None:
        return {"success": True, "message": "User already has Lifetime subscription."}
    
    base_time = max(user.expires_at, datetime.datetime.utcnow())
    user.expires_at = base_time + datetime.timedelta(days=data.days)
    db.commit()

    log_audit(db, user.app_id, "EXTEND_SUB", username=user.username, details=f"Extended by {data.days} days", status="SUCCESS")
    return {"success": True, "message": f"Extended '{user.username}' by {data.days} days", "new_expiry": user.expires_at.isoformat()}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    user = db.query(User).join(Application).filter(
        User.id == user_id,
        Application.developer_id == dev.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"success": True, "message": "User deleted successfully"}

@router.post("/users/bulk-delete")
async def bulk_delete_users(data: BulkDeleteUsersRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    users = db.query(User).join(Application).filter(
        User.id.in_(data.user_ids),
        Application.developer_id == dev.id
    ).all()
    count = len(users)
    for u in users:
        db.delete(u)
    db.commit()
    return {"success": True, "message": f"Successfully deleted {count} user(s)."}

@router.post("/users/purge-expired")
async def purge_expired_users(data: PurgeExpiredUsersRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    now = datetime.datetime.utcnow()
    expired_users = db.query(User).filter(
        User.app_id == app.id,
        User.expires_at != None,
        User.expires_at < now
    ).all()
    
    count = len(expired_users)
    for u in expired_users:
        db.delete(u)
    db.commit()
    
    log_audit(db, app.id, "PURGE_EXPIRED", username=dev.username, details=f"Purged {count} expired user accounts", status="DANGER")
    return {"success": True, "message": f"Purged {count} expired user account(s)."}

@router.post("/users/reset-all-hwid")
async def reset_all_hwid(data: ResetAllHwidRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    users = db.query(User).filter(User.app_id == app.id, User.hwid != None).all()
    count = len(users)
    for u in users:
        u.hwid = None
    db.commit()
    
    log_audit(db, app.id, "RESET_ALL_HWID", username=dev.username, details=f"Reset HWID lock for all {count} users", status="WARNING")
    return {"success": True, "message": f"Reset HWID lock for {count} user(s) in {app.name}."}

@router.post("/users/bulk-extend")
async def bulk_extend_users(data: BulkExtendUsersRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    query = db.query(User).filter(User.app_id == app.id)
    if data.user_ids and len(data.user_ids) > 0:
        query = query.filter(User.id.in_(data.user_ids))
    
    users = query.all()
    count = 0
    now = datetime.datetime.utcnow()
    for u in users:
        if u.expires_at is not None:
            base = max(u.expires_at, now)
            u.expires_at = base + datetime.timedelta(days=data.days)
            count += 1
    db.commit()
    
    log_audit(db, app.id, "BULK_EXTEND", username=dev.username, details=f"Extended {count} user(s) by {data.days} days", status="SUCCESS")
    return {"success": True, "message": f"Extended subscription by {data.days} days for {count} user(s)."}

@router.post("/users/bulk-ban")
async def bulk_ban_users(data: BulkBanUsersRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    users = db.query(User).join(Application).filter(
        User.id.in_(data.user_ids),
        Application.developer_id == dev.id
    ).all()
    count = len(users)
    for u in users:
        u.is_banned = True
        u.ban_reason = data.reason or "Bulk banned by developer"
    db.commit()
    return {"success": True, "message": f"Banned {count} user account(s)."}

# ==================== 4. SUBSCRIPTION TIERS & RANKS ====================
@router.get("/tiers")
async def list_tiers(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "tiers": []}
    tiers = db.query(SubscriptionTier).filter(SubscriptionTier.app_id == app_id).all()
    return {"success": True, "tiers": [
        {"id": t.id, "name": t.name, "level_rank": t.level_rank, "description": t.description}
        for t in tiers
    ]}

@router.post("/tiers")
async def create_tier(data: CreateTierRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    tier = SubscriptionTier(
        app_id=data.app_id,
        name=data.name.strip(),
        level_rank=data.level_rank or 1,
        description=data.description or ""
    )
    db.add(tier)
    db.commit()
    return {"success": True, "message": f"Subscription Tier '{tier.name}' created"}

@router.delete("/tiers/{tier_id}")
async def delete_tier(tier_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    tier = db.query(SubscriptionTier).join(Application).filter(
        SubscriptionTier.id == tier_id,
        Application.developer_id == dev.id
    ).first()
    if not tier:
        raise HTTPException(status_code=404, detail="Tier not found")
    db.delete(tier)
    db.commit()
    return {"success": True, "message": "Tier deleted successfully"}

# ==================== 5. CLOUD VARIABLES ====================
@router.get("/variables")
async def list_variables(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "variables": []}
    
    vars_list = db.query(AppVariable).filter(AppVariable.app_id == app_id).all()
    return {
        "success": True,
        "variables": [
            {
                "id": v.id,
                "app_id": v.app_id,
                "name": v.name,
                "value": v.value,
                "is_encrypted": v.is_encrypted,
                "created_at": v.created_at.isoformat()
            }
            for v in vars_list
        ]
    }

@router.post("/variables")
async def create_variable(data: CreateVariableRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    existing = db.query(AppVariable).filter(AppVariable.app_id == data.app_id, AppVariable.name == data.name.strip()).first()
    if existing:
        existing.value = data.value
        existing.is_encrypted = data.is_encrypted
        db.commit()
        return {"success": True, "message": "Variable updated successfully"}
    
    new_var = AppVariable(
        app_id=data.app_id,
        name=data.name.strip(),
        value=data.value,
        is_encrypted=data.is_encrypted
    )
    db.add(new_var)
    db.commit()
    return {"success": True, "message": "Variable created successfully"}

@router.delete("/variables/{var_id}")
async def delete_variable(var_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    var_obj = db.query(AppVariable).join(Application).filter(
        AppVariable.id == var_id,
        Application.developer_id == dev.id
    ).first()
    if not var_obj:
        raise HTTPException(status_code=404, detail="Variable not found")
    db.delete(var_obj)
    db.commit()
    return {"success": True, "message": "Variable deleted"}

# ==================== 6. FILES & LOADER CDN ====================
@router.get("/files")
async def list_files(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "files": []}
    files = db.query(AppFile).filter(AppFile.app_id == app_id).all()
    return {"success": True, "files": [
        {"id": f.id, "file_id": f.file_id, "file_name": f.file_name, "file_url": f.file_url, "file_size": f.file_size, "auth_required": f.auth_required}
        for f in files
    ]}

@router.post("/files")
async def create_file(data: CreateFileRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    app_file = AppFile(
        app_id=data.app_id,
        file_id=data.file_id.strip(),
        file_name=data.file_name.strip(),
        file_url=data.file_url.strip(),
        file_size=data.file_size or 0,
        auth_required=True
    )
    db.add(app_file)
    db.commit()
    return {"success": True, "message": f"File '{app_file.file_name}' added to CDN"}

@router.delete("/files/{file_id}")
async def delete_file(file_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app_file = db.query(AppFile).join(Application).filter(
        AppFile.id == file_id,
        Application.developer_id == dev.id
    ).first()
    if not app_file:
        raise HTTPException(status_code=404, detail="File not found")
    db.delete(app_file)
    db.commit()
    return {"success": True, "message": "File deleted successfully"}

# ==================== 7. BLACKLISTS (IP / HWID) ====================
@router.get("/blacklists")
async def list_blacklists(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "blacklists": []}
    blacklists = db.query(Blacklist).filter(Blacklist.app_id == app_id).all()
    return {"success": True, "blacklists": [
        {"id": b.id, "type": b.type, "data": b.data, "reason": b.reason, "created_at": b.created_at.isoformat()}
        for b in blacklists
    ]}

@router.post("/blacklists")
async def create_blacklist(data: CreateBlacklistRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    bl = Blacklist(
        app_id=data.app_id,
        type=data.type.lower(),
        data=data.data.strip(),
        reason=data.reason or "Blacklisted by Admin"
    )
    db.add(bl)
    db.commit()
    return {"success": True, "message": f"{data.type.upper()} added to blacklist"}

@router.delete("/blacklists/{bl_id}")
async def delete_blacklist(bl_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    bl = db.query(Blacklist).join(Application).filter(
        Blacklist.id == bl_id,
        Application.developer_id == dev.id
    ).first()
    if not bl:
        raise HTTPException(status_code=404, detail="Blacklist entry not found")
    db.delete(bl)
    db.commit()
    return {"success": True, "message": "Removed from blacklist"}

# ==================== 8. RESELLERS ====================
@router.get("/resellers")
async def list_resellers(dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    resellers = db.query(Reseller).filter(Reseller.developer_id == dev.id).all()
    results = []
    for r in resellers:
        total_keys = db.query(License).filter(License.created_by_reseller == r.username).count()
        used_keys = db.query(License).filter(License.created_by_reseller == r.username, License.status == "used").count()
        unused_keys = db.query(License).filter(License.created_by_reseller == r.username, License.status == "unused").count()
        results.append({
            "id": r.id,
            "username": r.username,
            "balance": r.balance,
            "allowed_apps": r.allowed_apps,
            "created_at": r.created_at.isoformat(),
            "total_keys": total_keys,
            "used_keys": used_keys,
            "unused_keys": unused_keys
        })
    return {"success": True, "resellers": results}

@router.post("/resellers")
async def create_reseller(data: CreateResellerRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    existing = db.query(Reseller).filter(Reseller.developer_id == dev.id, Reseller.username == data.username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Reseller username already exists")
    
    reseller = Reseller(
        developer_id=dev.id,
        username=data.username.strip(),
        password_hash=hash_password(data.password),
        balance=data.balance or 50,
        allowed_apps=data.allowed_apps or "all"
    )
    db.add(reseller)
    db.commit()
    return {"success": True, "message": f"Reseller '{reseller.username}' created with {reseller.balance} credits"}

@router.patch("/resellers/{reseller_id}/credits")
async def update_reseller_credits(reseller_id: int, data: UpdateResellerCreditsRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    
    if data.operation == "add":
        reseller.balance += data.amount
    elif data.operation == "deduct":
        reseller.balance = max(0, reseller.balance - data.amount)
    elif data.operation == "set":
        reseller.balance = max(0, data.amount)
    
    db.commit()
    return {"success": True, "message": f"Updated '{reseller.username}' balance to {reseller.balance} credits", "new_balance": reseller.balance}

@router.patch("/resellers/{reseller_id}/password")
async def reset_reseller_password(reseller_id: int, data: ResetResellerPasswordRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    if len(data.new_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")
    
    reseller.password_hash = hash_password(data.new_password)
    db.commit()
    return {"success": True, "message": f"Password updated for reseller '{reseller.username}'"}

@router.get("/resellers/{reseller_id}/licenses")
async def get_reseller_generated_licenses(reseller_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    
    keys = db.query(License).filter(License.created_by_reseller == reseller.username).order_by(License.created_at.desc()).all()
    return {
        "success": True,
        "reseller_username": reseller.username,
        "licenses": [
            {
                "id": k.id,
                "app_name": k.app.name if k.app else "Unknown",
                "key": k.license_key,
                "duration_days": k.duration_days,
                "status": k.status,
                "used_by": k.used_by_username or "-",
                "created_at": k.created_at.isoformat()
            }
            for k in keys
        ]
    }

@router.delete("/resellers/{reseller_id}")
async def delete_reseller(reseller_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    db.delete(reseller)
    db.commit()
    return {"success": True, "message": "Reseller deleted"}

# ==================== 9. WEBHOOKS & TEST ====================
@router.post("/webhooks/test")
async def test_webhook(data: TestWebhookRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if not app.webhook_url:
        raise HTTPException(status_code=400, detail="No Discord webhook configured for this application")
    
    send_discord_webhook(app.webhook_url, app.name, "TEST_WEBHOOK", dev.username, "127.0.0.1", "SUCCESS", data.custom_message)
    return {"success": True, "message": "Discord Webhook test notification dispatched"}

class RedeemPlanKeyRequest(BaseModel):
    key_code: str

# ==================== 10. PLAN UPGRADE & REDEEM ====================
@router.post("/plan/redeem")
async def redeem_plan_key(data: RedeemPlanKeyRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    key_code = data.key_code.strip().upper()
    if not key_code:
        raise HTTPException(status_code=400, detail="Please enter a valid Upgrade License Key")
    
    # 1. Check database PlanKey
    plan_key = db.query(PlanKey).filter(PlanKey.key_code == key_code, PlanKey.is_used == False).first()
    
    target_plan = None
    if plan_key:
        target_plan = plan_key.target_plan
        plan_key.is_used = True
        plan_key.used_by_username = dev.username
    elif key_code.startswith("JOYST-PAID-") or key_code.startswith("JOYST-PRO-") or key_code.startswith("JOYST-DEV-") or key_code.startswith("JOYST-ENT-") or key_code == "PAID-UPGRADE-2026":
        target_plan = "Paid"
    else:
        raise HTTPException(status_code=400, detail="Invalid or already redeemed Upgrade Key. Purchase a valid Paid Plan key from Joyst Corporation.")

    if target_plan in ["Developer", "Enterprise"]:
        target_plan = "Paid"

    dev.plan = "Paid"
    dev.max_apps = 999999
    dev.max_users_per_app = 999999

    db.commit()
    return {"success": True, "message": "Successfully activated Paid Pro Plan for your account! All limits unlocked.", "plan": dev.plan}

class GeneratePlanKeyRequest(BaseModel):
    target_plan: Optional[str] = "Paid"
    count: Optional[int] = 1

@router.post("/plan/generate-keys")
async def generate_plan_keys(data: GeneratePlanKeyRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    target_plan = "Paid"
    count = min(max(1, data.count or 1), 50)
    generated_keys = []
    
    for _ in range(count):
        token = generate_random_token(12).upper()
        # Format: JOYST-PAID-XXXX-XXXX-XXXX
        key_code = f"JOYST-PAID-{token[:4]}-{token[4:8]}-{token[8:12]}"
        
        plan_key = PlanKey(
            key_code=key_code,
            target_plan=target_plan,
            is_used=False
        )
        db.add(plan_key)
        generated_keys.append(key_code)
        
    db.commit()
    return {
        "success": True,
        "message": f"Generated {len(generated_keys)} Paid Plan Upgrade Key(s)",
        "keys": generated_keys
    }

# ==================== 11. AUDIT LOGS & STATS ====================
@router.get("/logs")
async def get_audit_logs(
    app_id: int,
    search: Optional[str] = None,
    limit: int = 100,
    dev: Developer = Depends(get_current_developer),
    db: Session = Depends(get_db)
):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        return {"success": True, "logs": []}

    query = db.query(AuditLog).filter(AuditLog.app_id == app_id)
    if search:
        query = query.filter(
            (AuditLog.username.contains(search)) |
            (AuditLog.ip_address.contains(search)) |
            (AuditLog.action.contains(search)) |
            (AuditLog.details.contains(search))
        )
    logs = query.order_by(desc(AuditLog.timestamp)).limit(limit).all()
    return {
        "success": True,
        "logs": [
            {
                "id": l.id,
                "app_id": l.app_id,
                "app_name": app.name,
                "username": l.username,
                "action": l.action,
                "ip_address": l.ip_address,
                "hwid": l.hwid,
                "details": l.details,
                "status": l.status,
                "timestamp": l.timestamp.isoformat()
            }
            for l in logs
        ]
    }

@router.delete("/logs/clear")
async def clear_audit_logs(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    deleted = db.query(AuditLog).filter(AuditLog.app_id == app_id).delete()
    db.commit()
    return {"success": True, "message": f"Cleared {deleted} audit log entries"}

@router.get("/stats")
async def get_developer_stats(dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    dev_apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    app_ids = [a.id for a in dev_apps]
    
    total_apps = len(dev_apps)
    total_users = db.query(User).filter(User.app_id.in_(app_ids)).count() if app_ids else 0
    total_licenses = db.query(License).filter(License.app_id.in_(app_ids)).count() if app_ids else 0
    unused_licenses = db.query(License).filter(License.app_id.in_(app_ids), License.status == "unused").count() if app_ids else 0
    banned_users = db.query(User).filter(User.app_id.in_(app_ids), User.is_banned == True).count() if app_ids else 0
    total_files = db.query(AppFile).filter(AppFile.app_id.in_(app_ids)).count() if app_ids else 0
    total_blacklists = db.query(Blacklist).filter(Blacklist.app_id.in_(app_ids)).count() if app_ids else 0
    
    today = datetime.datetime.utcnow().date()
    today_start = datetime.datetime.combine(today, datetime.time.min)
    logins_today = db.query(AuditLog).filter(AuditLog.app_id.in_(app_ids), AuditLog.action == "LOGIN_SUCCESS", AuditLog.timestamp >= today_start).count() if app_ids else 0
    failed_logins_today = db.query(AuditLog).filter(
        AuditLog.app_id.in_(app_ids),
        (AuditLog.action == "LOGIN_FAILED") | (AuditLog.action == "HWID_MISMATCH"),
        AuditLog.timestamp >= today_start
    ).count() if app_ids else 0

    recent_logs = db.query(AuditLog).filter(AuditLog.app_id.in_(app_ids)).order_by(desc(AuditLog.timestamp)).limit(10).all() if app_ids else []

    return {
        "success": True,
        "owner_id": dev.owner_id,
        "username": dev.username,
        "plan": dev.plan,
        "max_apps": dev.max_apps,
        "stats": {
            "total_apps": total_apps,
            "total_users": total_users,
            "total_licenses": total_licenses,
            "unused_licenses": unused_licenses,
            "banned_users": banned_users,
            "total_files": total_files,
            "total_blacklists": total_blacklists,
            "logins_today": logins_today,
            "failed_logins_today": failed_logins_today
        },
        "recent_activity": [
            {
                "id": l.id,
                "app_name": l.app.name if l.app else "System",
                "username": l.username,
                "action": l.action,
                "ip": l.ip_address,
                "status": l.status,
                "time": l.timestamp.strftime("%H:%M:%S - %d %b")
            }
            for l in recent_logs
        ]
    }

# ==================== DISCORD BOT AUTO-FETCH API ====================
class BotGenKeyRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    count: int = 1
    duration_days: int = 30
    level: str = "default"
    mask: str = "JOYST-XXXX-XXXX-XXXX"

@router.post("/bot/genkey")
async def bot_auto_genkey(data: BotGenKeyRequest, db: Session = Depends(get_db)):
    """Auto-detects developer by Discord ID and generates licenses instantly."""
    d_id = str(data.discord_id).strip()
    d_user = (data.discord_username or "").strip()

    dev = None
    if d_id:
        dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev and d_user:
        dev = db.query(Developer).filter(Developer.username == d_user).first()
    if not dev and d_user:
        dev = db.query(Developer).filter(Developer.email.like(f"{d_user}%")).first()

    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Please run `/link [email_or_username]` first.")

    # Strict Paid Plan Verification
    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    # Select app
    app = None
    if data.app_name:
        app = db.query(Application).filter(Application.developer_id == dev.id, Application.name.ilike(data.app_name)).first()
    if not app:
        app = db.query(Application).filter(Application.developer_id == dev.id).order_by(Application.id.asc()).first()

    if not app:
        # Auto-create default app if none exists
        app = Application(
            developer_id=dev.id,
            name="JOYST",
            owner_id=dev.owner_id,
            secret="sec_" + generate_random_token(32),
            version="1.0",
            status="enabled"
        )
        db.add(app)
        db.commit()
        db.refresh(app)

    count = min(max(1, data.count), 50)
    created_keys = []
    for _ in range(count):
        k = generate_license_key(data.mask)
        lic = License(
            app_id=app.id,
            license_key=k,
            duration_days=data.duration_days,
            level=data.level,
            level_rank=1,
            notes=f"Auto-generated via Discord Bot for {data.discord_username or dev.username}"
        )
        db.add(lic)
        created_keys.append(k)

    db.commit()
    log_audit(db, app.id, "KEYS_GENERATED", details=f"Generated {len(created_keys)} key(s) via Discord Bot for {dev.username}", status="SUCCESS")

    return {
        "success": True,
        "developer": dev.username,
        "plan": dev.plan,
        "app_name": app.name,
        "app_id": app.id,
        "keys": created_keys,
        "count": len(created_keys),
        "duration_days": data.duration_days,
        "level": data.level
    }

class BotLinkRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    email_or_username: str
    password: Optional[str] = None
    owner_id: Optional[str] = None

@router.post("/bot/link")
async def bot_link_account(data: BotLinkRequest, db: Session = Depends(get_db)):
    """Allows Google or Username developers to link their Discord ID to their account in 1-click."""
    ident = data.email_or_username.strip()
    dev = db.query(Developer).filter(
        (Developer.email.ilike(ident)) |
        (Developer.username.ilike(ident)) |
        (Developer.owner_id == ident)
    ).first()

    if not dev:
        raise HTTPException(status_code=404, detail=f"No account found matching '{ident}'. Make sure you registered on joystauth.cc")

    dev.discord_id = str(data.discord_id).strip()
    db.commit()

    return {
        "success": True,
        "message": f"Successfully linked Discord @{data.discord_username or data.discord_id} to Developer Account @{dev.username}!",
        "developer": dev.username,
        "email": dev.email or "Google Auth",
        "plan": dev.plan
    }

class BotCreateUserRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    username: str
    password: str
    duration_days: int = 30
    subscription_tier: Optional[str] = "default"
    level: Optional[int] = 1

@router.post("/bot/adduser")
async def bot_add_user(data: BotCreateUserRequest, db: Session = Depends(get_db)):
    """Create user and password directly via Discord Bot."""
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    app = None
    if data.app_name:
        app = db.query(Application).filter(Application.developer_id == dev.id, Application.name.ilike(data.app_name)).first()
    if not app:
        app = db.query(Application).filter(Application.developer_id == dev.id).first()

    if not app:
        raise HTTPException(status_code=404, detail="No application found in your workspace. Create an app first.")

    existing = db.query(User).filter(User.app_id == app.id, User.username == data.username.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"User '{data.username}' already exists in application '{app.name}'.")

    expires_at = None
    if data.duration_days > 0:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=data.duration_days)

    new_user = User(
        app_id=app.id,
        username=data.username.strip(),
        password_hash=hash_password(data.password),
        subscription_tier=data.subscription_tier or "default",
        level=data.level or 1,
        expires_at=expires_at,
        registered_ip="Discord Bot",
        key_used="Manual by Discord Bot"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(db, app.id, "MANUAL_USER_CREATE", username=new_user.username, details=f"Created via Discord Bot by @{data.discord_username or dev.username}", status="SUCCESS")

    return {
        "success": True,
        "message": f"Client user '{new_user.username}' created successfully.",
        "username": new_user.username,
        "app_name": app.name,
        "duration_days": data.duration_days,
        "subscription": new_user.subscription_tier,
        "expires_at": new_user.expires_at.strftime("%Y-%m-%d %H:%M UTC") if new_user.expires_at else "Lifetime"
    }

class BotUserActionRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    target_username: str
    reason: Optional[str] = "Admin action via Discord Bot"

@router.post("/bot/resethwid")
async def bot_reset_hwid(data: BotUserActionRequest, db: Session = Depends(get_db)):
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = data.target_username.strip()
    user = db.query(User).join(Application).filter(
        Application.developer_id == dev.id,
        User.username.ilike(target)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail=f"User '{target}' not found in your apps.")

    user.hwid = None
    db.commit()
    log_audit(db, user.app_id, "HWID_RESET", username=user.username, details=f"HWID reset via Discord Bot by {data.discord_username or dev.username}", status="SUCCESS")

    return {"success": True, "message": f"HWID for user '{user.username}' reset successfully.", "username": user.username, "app_name": user.app.name}

@router.post("/bot/ban")
async def bot_ban_user(data: BotUserActionRequest, db: Session = Depends(get_db)):
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = data.target_username.strip()
    user = db.query(User).join(Application).filter(
        Application.developer_id == dev.id,
        User.username.ilike(target)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail=f"User '{target}' not found.")

    user.is_banned = True
    user.ban_reason = data.reason or "Banned via Discord Bot"
    db.commit()
    log_audit(db, user.app_id, "BAN_USER", username=user.username, details=user.ban_reason, status="DANGER")

    return {"success": True, "message": f"User '{user.username}' banned successfully.", "username": user.username, "reason": user.ban_reason}

@router.post("/bot/unban")
async def bot_unban_user(data: BotUserActionRequest, db: Session = Depends(get_db)):
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = data.target_username.strip()
    user = db.query(User).join(Application).filter(
        Application.developer_id == dev.id,
        User.username.ilike(target)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail=f"User '{target}' not found.")

    user.is_banned = False
    user.ban_reason = ""
    db.commit()
    log_audit(db, user.app_id, "UNBAN_USER", username=user.username, details="Unbanned via Discord Bot", status="SUCCESS")

    return {"success": True, "message": f"User '{user.username}' unbanned successfully.", "username": user.username}

@router.post("/bot/userinfo")
async def bot_user_info(data: BotUserActionRequest, db: Session = Depends(get_db)):
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = data.target_username.strip()
    user = db.query(User).join(Application).filter(
        Application.developer_id == dev.id,
        User.username.ilike(target)
    ).first()

    if not user:
        raise HTTPException(status_code=404, detail=f"User '{target}' not found.")

    return {
        "success": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "app_name": user.app.name,
            "hwid": user.hwid or "Not Bound",
            "last_ip": user.last_ip or "Unknown",
            "subscription": user.subscription_tier,
            "level": user.level,
            "expires_at": user.expires_at.isoformat() if user.expires_at else "Lifetime",
            "is_banned": user.is_banned,
            "ban_reason": user.ban_reason,
            "created_at": user.created_at.isoformat() if user.created_at else "Unknown"
        }
    }

class BotStatsRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""

@router.post("/bot/stats")
async def bot_get_stats(data: BotStatsRequest, db: Session = Depends(get_db)):
    d_id = str(data.discord_id).strip()
    dev = db.query(Developer).filter(Developer.discord_id == d_id).first()
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    app_ids = [a.id for a in apps]

    total_users = db.query(User).filter(User.app_id.in_(app_ids)).count() if app_ids else 0
    total_keys = db.query(License).filter(License.app_id.in_(app_ids)).count() if app_ids else 0
    unused_keys = db.query(License).filter(License.app_id.in_(app_ids), License.status == "unused").count() if app_ids else 0
    banned_users = db.query(User).filter(User.app_id.in_(app_ids), User.is_banned == True).count() if app_ids else 0

    return {
        "success": True,
        "developer": dev.username,
        "plan": dev.plan,
        "total_apps": len(apps),
        "apps_list": [a.name for a in apps],
        "total_users": total_users,
        "total_keys": total_keys,
        "unused_keys": unused_keys,
        "banned_users": banned_users
    }
