import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt

from ..database import get_db, Developer, Application, License, User, Reseller
from ..security import verify_password, hash_password, create_access_token, decode_access_token, generate_license_key
from ..config import log_audit

router = APIRouter(prefix="/api/v1/reseller", tags=["Joyst Corporation Reseller API"])

class ResellerLoginRequest(BaseModel):
    username: str
    password: str

class ResellerGenKeysRequest(BaseModel):
    app_id: int
    count: int = 1
    duration_days: int = 30
    level: Optional[str] = "default"
    mask: Optional[str] = "JOYST-XXXX-XXXX-XXXX"
    notes: Optional[str] = ""

class ResellerCreateUserRequest(BaseModel):
    app_id: int
    username: str
    password: str
    duration_days: int = 30
    level: Optional[str] = "default"
    notes: Optional[str] = ""

class ResellerEditUserPasswordRequest(BaseModel):
    new_password: str

class ResellerBanUserRequest(BaseModel):
    reason: Optional[str] = "Banned by Reseller"

class ResellerHwidResetRequest(BaseModel):
    app_id: int
    username: str

class ResellerExtendUserRequest(BaseModel):
    additional_days: int = 30

class ResellerBulkDeleteLicensesRequest(BaseModel):
    app_id: int
    delete_type: str # 'unused', 'used', 'all'

class ResellerBulkDeleteUsersRequest(BaseModel):
    app_id: int
    delete_type: str # 'expired', 'banned', 'all'

def get_current_reseller(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Reseller:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or payload.get("role") != "reseller":
        raise HTTPException(status_code=401, detail="Invalid reseller session token")
    
    try:
        reseller_id = int(payload.get("sub"))
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid reseller token subject")

    reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
    if not reseller:
        raise HTTPException(status_code=401, detail="Reseller account not found")
    return reseller

def check_app_access(reseller: Reseller, app_id: int, db: Session) -> Application:
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == reseller.developer_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    if "all" not in allowed_apps_raw and str(app.id) not in allowed_apps_raw and app.name not in allowed_apps_raw:
        raise HTTPException(status_code=403, detail="You do not have permission to manage this application")
    return app

@router.post("/login")
async def reseller_login(data: ResellerLoginRequest, db: Session = Depends(get_db)):
    reseller = db.query(Reseller).filter(Reseller.username == data.username.strip()).first()
    if not reseller or not verify_password(data.password, reseller.password_hash):
        raise HTTPException(status_code=400, detail="Invalid reseller username or password")
    
    token = create_access_token({"sub": str(reseller.id), "username": reseller.username, "role": "reseller"})
    return {
        "success": True,
        "token": token,
        "reseller": {
            "id": reseller.id,
            "username": reseller.username,
            "balance": reseller.balance,
            "allowed_apps": reseller.allowed_apps
        }
    }

@router.get("/me")
async def get_reseller_profile(reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    dev = db.query(Developer).filter(Developer.id == reseller.developer_id).first()
    all_dev_apps = db.query(Application).filter(Application.developer_id == reseller.developer_id).all()
    
    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    allowed_apps_list = []
    for app in all_dev_apps:
        if "all" in allowed_apps_raw or str(app.id) in allowed_apps_raw or app.name in allowed_apps_raw:
            user_count = db.query(User).filter(User.app_id == app.id).count()
            license_count = db.query(License).filter(License.app_id == app.id).count()
            allowed_apps_list.append({
                "id": app.id,
                "name": app.name,
                "version": app.version,
                "secret_token": app.secret_token,
                "status": app.custom_status or "ONLINE",
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "total_users": user_count,
                "total_licenses": license_count
            })

    return {
        "success": True,
        "reseller": {
            "id": reseller.id,
            "username": reseller.username,
            "balance": reseller.balance,
            "allowed_apps": reseller.allowed_apps,
            "developer_name": dev.username if dev else "Developer",
            "apps": allowed_apps_list
        }
    }

# ==================== LICENSE MANAGEMENT ====================

@router.get("/licenses")
async def list_reseller_licenses(
    app_id: Optional[int] = None,
    reseller: Reseller = Depends(get_current_reseller),
    db: Session = Depends(get_db)
):
    query = db.query(License).filter(License.created_by_reseller == reseller.username)
    if app_id:
        query = query.filter(License.app_id == app_id)
    keys = query.order_by(License.created_at.desc()).all()

    return {
        "success": True,
        "licenses": [
            {
                "id": k.id,
                "app_id": k.app_id,
                "app_name": k.app.name if k.app else "Unknown",
                "key": k.license_key,
                "duration_days": k.duration_days,
                "level": k.level,
                "status": k.status,
                "used_by": k.used_by_username or "-",
                "used_at": k.used_at.isoformat() if k.used_at else None,
                "created_at": k.created_at.isoformat(),
                "notes": k.notes or ""
            }
            for k in keys
        ]
    }

@router.post("/generate-keys")
async def reseller_generate_keys(data: ResellerGenKeysRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = check_app_access(reseller, data.app_id, db)
    
    if data.count < 1 or data.count > 500:
        raise HTTPException(status_code=400, detail="Key count must be between 1 and 500")

    if reseller.balance < data.count:
        raise HTTPException(status_code=400, detail=f"Insufficient key credits! You have {reseller.balance} credits, but requested {data.count}.")

    generated_keys = []
    mask = data.mask or "JOYST-XXXX-XXXX-XXXX"

    for _ in range(data.count):
        raw_key = generate_license_key(mask)
        while db.query(License).filter(License.app_id == app.id, License.license_key == raw_key).first():
            raw_key = generate_license_key(mask)

        lic = License(
            app_id=app.id,
            license_key=raw_key,
            duration_days=data.duration_days,
            level=data.level or "default",
            level_rank=1,
            status="unused",
            created_by_reseller=reseller.username,
            notes=data.notes or f"Generated by Reseller {reseller.username}"
        )
        db.add(lic)
        generated_keys.append(raw_key)

    reseller.balance -= data.count
    db.commit()

    log_audit(
        db,
        app.id,
        "KEYS_GENERATED",
        username=reseller.username,
        details=f"Reseller '{reseller.username}' generated {data.count} keys (Note: {data.notes or 'None'}, Balance: {reseller.balance})",
        status="SUCCESS"
    )

    return {
        "success": True,
        "message": f"Successfully generated {data.count} keys! Remaining balance: {reseller.balance} credits.",
        "keys": generated_keys,
        "app_name": app.name,
        "duration_days": data.duration_days,
        "notes": data.notes or "",
        "remaining_balance": reseller.balance
    }

@router.post("/licenses/{license_id}/toggle-pause")
async def toggle_license_pause(license_id: int, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id, License.created_by_reseller == reseller.username).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found or not owned by your reseller profile")

    if lic.status == "paused":
        lic.status = "unused" if not lic.used_by_username else "used"
    else:
        lic.status = "paused"

    db.commit()
    log_audit(db, lic.app_id, "LICENSE_PAUSE_TOGGLE", username=reseller.username, details=f"License {lic.license_key} status changed to {lic.status}")
    return {"success": True, "message": f"License status updated to {lic.status.upper()}", "new_status": lic.status}

@router.delete("/licenses/{license_id}")
async def delete_reseller_license(license_id: int, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    lic = db.query(License).filter(License.id == license_id, License.created_by_reseller == reseller.username).first()
    if not lic:
        raise HTTPException(status_code=404, detail="License not found or not owned by your reseller profile")

    db.delete(lic)
    db.commit()
    log_audit(db, lic.app_id, "LICENSE_DELETED", username=reseller.username, details=f"License {lic.license_key} deleted by reseller")
    return {"success": True, "message": "License deleted successfully"}

@router.post("/licenses/bulk-delete")
async def bulk_delete_reseller_licenses(data: ResellerBulkDeleteLicensesRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = check_app_access(reseller, data.app_id, db)
    
    query = db.query(License).filter(License.app_id == app.id, License.created_by_reseller == reseller.username)
    if data.delete_type == "unused":
        query = query.filter(License.status == "unused")
    elif data.delete_type == "used":
        query = query.filter(License.status == "used")
    elif data.delete_type == "paused":
        query = query.filter(License.status == "paused")
    elif data.delete_type != "all":
        raise HTTPException(status_code=400, detail="Invalid delete type")

    deleted_count = query.delete(synchronize_session=False)
    db.commit()

    log_audit(db, app.id, "BULK_DELETE_KEYS", username=reseller.username, details=f"Bulk deleted {deleted_count} {data.delete_type} keys")
    return {"success": True, "message": f"Successfully deleted {deleted_count} {data.delete_type} license(s)!"}

# ==================== USER MANAGEMENT ====================

@router.get("/users")
async def list_reseller_users(
    app_id: Optional[int] = None,
    reseller: Reseller = Depends(get_current_reseller),
    db: Session = Depends(get_db)
):
    all_dev_apps = db.query(Application).filter(Application.developer_id == reseller.developer_id).all()
    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    allowed_app_ids = [
        app.id for app in all_dev_apps
        if "all" in allowed_apps_raw or str(app.id) in allowed_apps_raw or app.name in allowed_apps_raw
    ]

    query = db.query(User).filter(User.app_id.in_(allowed_app_ids))
    if app_id:
        if app_id not in allowed_app_ids:
            raise HTTPException(status_code=403, detail="Permission denied for this application")
        query = query.filter(User.app_id == app_id)

    users = query.order_by(User.created_at.desc()).all()

    now = datetime.datetime.utcnow()
    user_list = []
    for u in users:
        is_expired = bool(u.expires_at and u.expires_at < now)
        raw_key = u.key_used or ""
        note = ""
        if "|NOTE:" in raw_key:
            note = raw_key.split("|NOTE:")[1].strip()
        elif "NOTE:" in raw_key:
            note = raw_key.split("NOTE:")[1].strip()

        time_left_str = "Lifetime VIP"
        if u.expires_at:
            if is_expired:
                time_left_str = "Expired"
            else:
                diff = u.expires_at - now
                time_left_str = f"{diff.days}d {diff.seconds // 3600}h left"

        user_list.append({
            "id": u.id,
            "app_id": u.app_id,
            "app_name": u.app.name if u.app else "Unknown",
            "username": u.username,
            "hwid": u.hwid or "Not Locked",
            "hwid_locked": bool(u.hwid),
            "subscription_tier": u.subscription_tier or "default",
            "expires_at": u.expires_at.isoformat() if u.expires_at else "Lifetime",
            "time_left": time_left_str,
            "is_expired": is_expired,
            "is_banned": u.is_banned,
            "ban_reason": u.ban_reason or "",
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "key_used": raw_key,
            "notes": note
        })

    return {
        "success": True,
        "users": user_list
    }

@router.post("/create-user")
async def reseller_create_user(data: ResellerCreateUserRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = check_app_access(reseller, data.app_id, db)
    
    if reseller.balance < 1:
        raise HTTPException(status_code=400, detail="Insufficient credits! You need at least 1 credit to create a user account.")

    clean_username = data.username.strip()
    clean_password = data.password.strip()
    clean_note = (data.notes or "").strip()

    if len(clean_username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters long")
    if len(clean_password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long")

    existing_user = db.query(User).filter(User.app_id == app.id, User.username == clean_username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail=f"Username '{clean_username}' already exists in this application!")

    if data.duration_days == -1:
        expires_at = None
    else:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=data.duration_days)

    pw_hash = hash_password(clean_password)

    key_tag = f"RESELLER:{reseller.username}"
    if clean_note:
        key_tag += f"|NOTE:{clean_note}"

    new_user = User(
        app_id=app.id,
        username=clean_username,
        password_hash=pw_hash,
        subscription_tier=data.level or "default",
        level=1,
        expires_at=expires_at,
        is_banned=False,
        key_used=key_tag,
        created_at=datetime.datetime.utcnow(),
        last_login=None
    )
    db.add(new_user)

    reseller.balance -= 1
    db.commit()

    log_audit(
        db,
        app.id,
        "USER_CREATED",
        username=clean_username,
        details=f"User account '{clean_username}' created by Reseller '{reseller.username}' (Note: {clean_note or 'None'}, Duration: {data.duration_days} days, Remaining Credits: {reseller.balance})",
        status="SUCCESS"
    )

    return {
        "success": True,
        "message": f"Customer user account '{clean_username}' created successfully! (1 Credit deducted, Balance: {reseller.balance})",
        "user": {
            "id": new_user.id,
            "username": clean_username,
            "password": clean_password,
            "app_name": app.name,
            "duration_days": data.duration_days,
            "expires_at": expires_at.isoformat() if expires_at else "Lifetime",
            "notes": clean_note
        },
        "remaining_balance": reseller.balance
    }

@router.post("/users/{user_id}/toggle-ban")
async def toggle_ban_reseller_user(
    user_id: int,
    data: Optional[ResellerBanUserRequest] = None,
    reseller: Reseller = Depends(get_current_reseller),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    check_app_access(reseller, user.app_id, db)

    user.is_banned = not user.is_banned
    if user.is_banned:
        user.ban_reason = (data.reason if data else None) or f"Banned by Reseller {reseller.username}"
        log_audit(db, user.app_id, "USER_BANNED", username=user.username, details=f"Banned: {user.ban_reason}", status="DANGER")
    else:
        user.ban_reason = ""
        log_audit(db, user.app_id, "USER_UNBANNED", username=user.username, details=f"Unbanned by Reseller {reseller.username}", status="SUCCESS")

    db.commit()
    return {
        "success": True,
        "message": f"User '{user.username}' is now {'BANNED' if user.is_banned else 'ACTIVE'}",
        "is_banned": user.is_banned
    }

@router.post("/users/{user_id}/reset-hwid")
async def reseller_user_reset_hwid(user_id: int, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    check_app_access(reseller, user.app_id, db)

    old_hwid = user.hwid
    user.hwid = None
    db.commit()

    log_audit(db, user.app_id, "HWID_RESET", username=user.username, details=f"HWID reset performed by Reseller '{reseller.username}'")
    return {"success": True, "message": f"HWID lock successfully reset for '{user.username}'!"}

@router.post("/users/{user_id}/extend")
async def reseller_user_extend(user_id: int, data: ResellerExtendUserRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    check_app_access(reseller, user.app_id, db)

    if reseller.balance < 1:
        raise HTTPException(status_code=400, detail="Insufficient credits! (1 Credit required to extend subscription)")

    now = datetime.datetime.utcnow()
    base_time = user.expires_at if (user.expires_at and user.expires_at > now) else now
    user.expires_at = base_time + datetime.timedelta(days=data.additional_days)

    reseller.balance -= 1
    db.commit()

    log_audit(db, user.app_id, "USER_EXTENDED", username=user.username, details=f"Extended by {data.additional_days} days by Reseller '{reseller.username}'")
    return {
        "success": True,
        "message": f"User '{user.username}' extended by {data.additional_days} days! (Remaining Credits: {reseller.balance})",
        "new_expires_at": user.expires_at.isoformat(),
        "remaining_balance": reseller.balance
    }

@router.post("/users/{user_id}/edit-password")
async def reseller_user_edit_password(user_id: int, data: ResellerEditUserPasswordRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    check_app_access(reseller, user.app_id, db)

    clean_pwd = data.new_password.strip()
    if len(clean_pwd) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters long")

    user.password_hash = hash_password(clean_pwd)
    db.commit()

    log_audit(db, user.app_id, "PASSWORD_CHANGED", username=user.username, details=f"Password updated by Reseller '{reseller.username}'")
    return {"success": True, "message": f"Password for user '{user.username}' updated successfully!"}

@router.delete("/users/{user_id}")
async def reseller_user_delete(user_id: int, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    check_app_access(reseller, user.app_id, db)

    uname = user.username
    app_id = user.app_id
    db.delete(user)
    db.commit()

    log_audit(db, app_id, "USER_DELETED", username=uname, details=f"User deleted by Reseller '{reseller.username}'")
    return {"success": True, "message": f"User '{uname}' permanently deleted!"}

@router.post("/users/bulk-delete")
async def bulk_delete_reseller_users(data: ResellerBulkDeleteUsersRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = check_app_access(reseller, data.app_id, db)

    now = datetime.datetime.utcnow()
    query = db.query(User).filter(User.app_id == app.id)

    if data.delete_type == "expired":
        query = query.filter(User.expires_at.isnot(None), User.expires_at < now)
    elif data.delete_type == "banned":
        query = query.filter(User.is_banned == True)
    elif data.delete_type != "all":
        raise HTTPException(status_code=400, detail="Invalid delete type")

    deleted_count = query.delete(synchronize_session=False)
    db.commit()

    log_audit(db, app.id, "BULK_DELETE_USERS", username=reseller.username, details=f"Bulk deleted {deleted_count} {data.delete_type} users")
    return {"success": True, "message": f"Successfully deleted {deleted_count} {data.delete_type} user(s)!"}

# Legacy HWID reset endpoint
@router.post("/reset-hwid")
async def reseller_reset_hwid(data: ResellerHwidResetRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = check_app_access(reseller, data.app_id, db)
    user = db.query(User).filter(User.app_id == app.id, User.username == data.username.strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this application")

    user.hwid = None
    db.commit()
    log_audit(db, app.id, "HWID_RESET", username=user.username, details=f"HWID reset by Reseller '{reseller.username}'")
    return {"success": True, "message": f"HWID lock successfully reset for user '{user.username}'!"}

# ==================== DIAGNOSTICS ====================

@router.get("/diagnostics")
async def reseller_diagnostics(query: str = Query(..., min_length=1), reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    all_dev_apps = db.query(Application).filter(Application.developer_id == reseller.developer_id).all()
    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    allowed_app_ids = [
        app.id for app in all_dev_apps
        if "all" in allowed_apps_raw or str(app.id) in allowed_apps_raw or app.name in allowed_apps_raw
    ]

    q = query.strip()
    now = datetime.datetime.utcnow()

    users = db.query(User).filter(
        User.app_id.in_(allowed_app_ids),
        (User.username.ilike(f"%{q}%")) | (User.key_used.ilike(f"%{q}%")) | (User.hwid.ilike(f"%{q}%"))
    ).all()

    licenses = db.query(License).filter(
        License.app_id.in_(allowed_app_ids),
        (License.license_key.ilike(f"%{q}%")) | (License.used_by_username.ilike(f"%{q}%")) | (License.notes.ilike(f"%{q}%"))
    ).all()

    found_users = []
    for u in users:
        is_expired = bool(u.expires_at and u.expires_at < now)
        remaining_str = "Lifetime Unlimited"
        if u.expires_at:
            if u.expires_at > now:
                diff = u.expires_at - now
                remaining_str = f"{diff.days}d {diff.seconds // 3600}h left"
            else:
                remaining_str = "Expired"

        raw_key = u.key_used or ""
        note = ""
        if "|NOTE:" in raw_key:
            note = raw_key.split("|NOTE:")[1].strip()

        found_users.append({
            "type": "USER_ACCOUNT",
            "id": u.id,
            "app_id": u.app_id,
            "app_name": u.app.name if u.app else "Unknown",
            "username": u.username,
            "hwid": u.hwid or "Unlocked",
            "hwid_locked": bool(u.hwid),
            "status": "EXPIRED" if is_expired else ("BANNED" if u.is_banned else "ACTIVE"),
            "expires_at": u.expires_at.isoformat() if u.expires_at else "Lifetime",
            "remaining_time": remaining_str,
            "last_login": u.last_login.isoformat() if u.last_login else "Never",
            "is_banned": u.is_banned,
            "notes": note
        })

    found_licenses = []
    for l in licenses:
        found_licenses.append({
            "type": "LICENSE_KEY",
            "id": l.id,
            "app_id": l.app_id,
            "app_name": l.app.name if l.app else "Unknown",
            "key": l.license_key,
            "duration_days": l.duration_days,
            "status": l.status.upper(),
            "used_by": l.used_by_username or "-",
            "created_at": l.created_at.isoformat(),
            "notes": l.notes or ""
        })

    return {
        "success": True,
        "results": {
            "users": found_users,
            "licenses": found_licenses
        }
    }
