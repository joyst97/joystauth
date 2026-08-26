import os
import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from ..database import get_db, Application, User, License, AppVariable, AppFile, AuditLog, Developer, SubscriptionTier, Blacklist, Reseller, PlanKey, AppNotification, CustomClient
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
    custom_status: Optional[str] = None
    hwid_lock_enabled: Optional[bool] = None
    allow_user_hwid_reset: Optional[bool] = None
    vpn_block_enabled: Optional[bool] = None
    hash_check_enabled: Optional[bool] = None
    app_hash: Optional[str] = None
    session_timeout_minutes: Optional[int] = None
    download_link: Optional[str] = None
    custom_message: Optional[str] = None

    # Custom Response Messages
    login_success_message: Optional[str] = None
    login_failed_message: Optional[str] = None
    user_not_found_message: Optional[str] = None
    hwid_mismatch_message: Optional[str] = None
    maintenance_message: Optional[str] = None
    expired_sub_message: Optional[str] = None
    banned_user_message: Optional[str] = None
    brute_force_ban_message: Optional[str] = None
    blacklist_message: Optional[str] = None
    invalid_license_message: Optional[str] = None
    used_license_message: Optional[str] = None
    paused_license_message: Optional[str] = None
    revoked_license_message: Optional[str] = None
    register_success_message: Optional[str] = None
    license_login_success_message: Optional[str] = None
    hash_mismatch_message: Optional[str] = None
    version_mismatch_message: Optional[str] = None
    vpn_blocked_message: Optional[str] = None

    webhook_url: Optional[str] = None
    webhook_bot_name: Optional[str] = None
    webhook_avatar_url: Optional[str] = None
    webhook_on_login: Optional[bool] = None
    webhook_on_register: Optional[bool] = None
    webhook_on_hwid_reset: Optional[bool] = None
    webhook_on_failed: Optional[bool] = None
    webhook_on_key_gen: Optional[bool] = None
    webhook_on_ban: Optional[bool] = None

class CreateNotificationRequest(BaseModel):
    app_id: int
    title: str
    message: str
    type: Optional[str] = "info" # info, success, warning, danger
    show_on_login: Optional[bool] = True

class UpdateNotificationRequest(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    type: Optional[str] = None
    is_active: Optional[bool] = None
    show_on_login: Optional[bool] = None

class CreateLicenseRequest(BaseModel):
    app_id: int
    count: int = 1
    amount: Optional[int] = None
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
    file_name: Optional[str] = None
    file_url: str
    file_size: Optional[int] = 0

class CreateBlacklistRequest(BaseModel):
    app_id: int
    type: str # ip, hwid
    data: str
    reason: Optional[str] = "Blacklisted by Admin"

class CreateCustomClientRequest(BaseModel):
    username: str
    password: str
    allowed_apps: str = "" # Comma-separated app IDs or names
    notes: Optional[str] = ""

class UpdateCustomClientRequest(BaseModel):
    password: Optional[str] = None
    allowed_apps: Optional[str] = None
    notes: Optional[str] = None

class CreateResellerRequest(BaseModel):
    username: str
    password: str
    balance: Optional[int] = 100
    balance_credits: Optional[int] = None
    app_id: Optional[int] = None
    allowed_apps: Optional[str] = "all"
    allowed_tiers: Optional[str] = "default,VIP"

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
    query = db.query(Application).filter(Application.developer_id == dev.id)
    if getattr(dev, "is_custom_client", False):
        allowed = getattr(dev, "allowed_apps_list", [])
        app_ids = [int(x) for x in allowed if x.isdigit()]
        app_names = [x for x in allowed if not x.isdigit()]
        query = query.filter((Application.id.in_(app_ids)) | (Application.name.in_(app_names)))
    apps = query.all()
    result = []
    for app in apps:
        result.append({
            "id": app.id,
            "name": app.name,
            "owner_id": app.owner_id,
            "secret": app.secret,
            "version": app.version,
            "status": app.status,
            "custom_status": getattr(app, "custom_status", "UNDETECTED") or "UNDETECTED",
            "hwid_lock_enabled": app.hwid_lock_enabled,
            "allow_user_hwid_reset": getattr(app, "allow_user_hwid_reset", False),
            "vpn_block_enabled": app.vpn_block_enabled,
            "hash_check_enabled": getattr(app, "hash_check_enabled", False),
            "app_hash": getattr(app, "app_hash", "") or "",
            "session_timeout_minutes": app.session_timeout_minutes,
            "download_link": app.download_link,
            "custom_message": app.custom_message,
            "login_success_message": getattr(app, "login_success_message", "Welcome back! Logged in successfully.") or "Welcome back! Logged in successfully.",
            "login_failed_message": getattr(app, "login_failed_message", "Invalid username or password.") or "Invalid username or password.",
            "user_not_found_message": getattr(app, "user_not_found_message", "Username does not exist.") or "Username does not exist.",
            "hwid_mismatch_message": getattr(app, "hwid_mismatch_message", "HWID Mismatch! Your account is locked to another computer.") or "HWID Mismatch! Your account is locked to another computer.",
            "maintenance_message": getattr(app, "maintenance_message", "Application is under maintenance. Please check back soon.") or "Application is under maintenance. Please check back soon.",
            "expired_sub_message": getattr(app, "expired_sub_message", "Your subscription has expired! Please renew.") or "Your subscription has expired! Please renew.",
            "banned_user_message": getattr(app, "banned_user_message", "Account is banned!") or "Account is banned!",
            "brute_force_ban_message": getattr(app, "brute_force_ban_message", "Too many invalid attempts! Your PC hardware and IP are permanently banned.") or "Too many invalid attempts! Your PC hardware and IP are permanently banned.",
            "blacklist_message": getattr(app, "blacklist_message", "Access Denied! Your IP or Machine HWID has been blacklisted.") or "Access Denied! Your IP or Machine HWID has been blacklisted.",
            "invalid_license_message": getattr(app, "invalid_license_message", "Invalid license key.") or "Invalid license key.",
            "used_license_message": getattr(app, "used_license_message", "This license key is already used.") or "This license key is already used.",
            "paused_license_message": getattr(app, "paused_license_message", "This license key is paused by administrator.") or "This license key is paused by administrator.",
            "revoked_license_message": getattr(app, "revoked_license_message", "This license key has been revoked.") or "This license key has been revoked.",
            "register_success_message": getattr(app, "register_success_message", "Account created successfully! You are now logged in.") or "Account created successfully! You are now logged in.",
            "license_login_success_message": getattr(app, "license_login_success_message", "License authenticated successfully!") or "License authenticated successfully!",
            "hash_mismatch_message": getattr(app, "hash_mismatch_message", "Executable integrity verification failed! Modified or cracked binary detected.") or "Executable integrity verification failed! Modified or cracked binary detected.",
            "version_mismatch_message": getattr(app, "version_mismatch_message", "Update required! Please download the latest version.") or "Update required! Please download the latest version.",
            "vpn_blocked_message": getattr(app, "vpn_blocked_message", "VPN or Proxy connections are strictly prohibited.") or "VPN or Proxy connections are strictly prohibited.",
            "webhook_url": app.webhook_url,
            "webhook_bot_name": getattr(app, "webhook_bot_name", "JOYST AUTH SHIELD") or "JOYST AUTH SHIELD",
            "webhook_avatar_url": getattr(app, "webhook_avatar_url", "https://joystauth.cc/static/img/joyst_logo.png") or "https://joystauth.cc/static/img/joyst_logo.png",
            "webhook_on_login": getattr(app, "webhook_on_login", True),
            "webhook_on_register": getattr(app, "webhook_on_register", True),
            "webhook_on_hwid_reset": getattr(app, "webhook_on_hwid_reset", True),
            "webhook_on_failed": getattr(app, "webhook_on_failed", True),
            "webhook_on_key_gen": getattr(app, "webhook_on_key_gen", True),
            "webhook_on_ban": getattr(app, "webhook_on_ban", True),
            "created_at": app.created_at.isoformat(),
            "stats": {
                "total_users": 0,
                "total_licenses": 0,
                "unused_licenses": 0,
                "total_files": 0,
                "total_vars": 0
            }
        })
    return {"success": True, "owner_id": dev.owner_id, "apps": result}

@router.post("/apps")
async def create_app(data: CreateAppRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Custom client accounts cannot create new applications. Please contact your master administrator.")
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
    try:
        from ..config import send_platform_master_alert
        from ..config import EMOJI
        send_platform_master_alert(
            title=f"{EMOJI['bolt']}  NEW APPLICATION INITIALIZED",
            description=(
                f"### {EMOJI['shield']} Protected Application Created!\n\n"
                f"{EMOJI['arrow']} **Application:** `**{new_app.name}**` {EMOJI['bolt']}\n"
                f"{EMOJI['arrow']} **Developer Owner:** `@{dev.username}` {EMOJI['bot']}\n"
                f"{EMOJI['arrow']} **Build Version:** `v{new_app.version}`\n"
                f"{EMOJI['arrow']} **Hardware Lock:** `{'Strict HWID Lock' if new_app.hwid_lock_enabled else 'Disabled'}`\n\n"
                f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                f"{EMOJI['dot']} *Ready for AES-256 binary protection and C++/C#/Python SDK integration!*"
            ),
            fields=[],
            color=0x8B5CF6
        )
    except Exception:
        pass

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
    if data.custom_status is not None:
        app.custom_status = data.custom_status
    if data.hwid_lock_enabled is not None:
        app.hwid_lock_enabled = data.hwid_lock_enabled
    if data.allow_user_hwid_reset is not None:
        app.allow_user_hwid_reset = data.allow_user_hwid_reset
    if data.vpn_block_enabled is not None:
        app.vpn_block_enabled = data.vpn_block_enabled
    if data.hash_check_enabled is not None:
        app.hash_check_enabled = data.hash_check_enabled
    if data.app_hash is not None:
        app.app_hash = data.app_hash.strip()
    if data.session_timeout_minutes is not None:
        app.session_timeout_minutes = data.session_timeout_minutes
    if data.download_link is not None:
        app.download_link = data.download_link
    if data.custom_message is not None:
        app.custom_message = data.custom_message
    if data.login_success_message is not None:
        app.login_success_message = data.login_success_message
    if data.login_failed_message is not None:
        app.login_failed_message = data.login_failed_message
    if data.user_not_found_message is not None:
        app.user_not_found_message = data.user_not_found_message
    if data.hwid_mismatch_message is not None:
        app.hwid_mismatch_message = data.hwid_mismatch_message
    if data.maintenance_message is not None:
        app.maintenance_message = data.maintenance_message
    if data.expired_sub_message is not None:
        app.expired_sub_message = data.expired_sub_message
    if data.banned_user_message is not None:
        app.banned_user_message = data.banned_user_message
    if data.brute_force_ban_message is not None:
        app.brute_force_ban_message = data.brute_force_ban_message
    if data.blacklist_message is not None:
        app.blacklist_message = data.blacklist_message
    if data.invalid_license_message is not None:
        app.invalid_license_message = data.invalid_license_message
    if data.used_license_message is not None:
        app.used_license_message = data.used_license_message
    if data.paused_license_message is not None:
        app.paused_license_message = data.paused_license_message
    if data.revoked_license_message is not None:
        app.revoked_license_message = data.revoked_license_message
    if data.register_success_message is not None:
        app.register_success_message = data.register_success_message
    if data.license_login_success_message is not None:
        app.license_login_success_message = data.license_login_success_message
    if data.hash_mismatch_message is not None:
        app.hash_mismatch_message = data.hash_mismatch_message
    if data.version_mismatch_message is not None:
        app.version_mismatch_message = data.version_mismatch_message
    if data.vpn_blocked_message is not None:
        app.vpn_blocked_message = data.vpn_blocked_message
    if data.webhook_url is not None:
        app.webhook_url = data.webhook_url.strip()
    if data.webhook_bot_name is not None:
        app.webhook_bot_name = data.webhook_bot_name.strip()
    if data.webhook_avatar_url is not None:
        app.webhook_avatar_url = data.webhook_avatar_url.strip()
    if data.webhook_on_login is not None:
        app.webhook_on_login = data.webhook_on_login
    if data.webhook_on_register is not None:
        app.webhook_on_register = data.webhook_on_register
    if data.webhook_on_hwid_reset is not None:
        app.webhook_on_hwid_reset = data.webhook_on_hwid_reset
    if data.webhook_on_failed is not None:
        app.webhook_on_failed = data.webhook_on_failed
    if data.webhook_on_key_gen is not None:
        app.webhook_on_key_gen = data.webhook_on_key_gen
    if data.webhook_on_ban is not None:
        app.webhook_on_ban = data.webhook_on_ban
    
    db.commit()
    return {"success": True, "message": "Application settings updated successfully"}

@router.post("/apps/{app_id}/toggle-maintenance")
async def toggle_app_maintenance(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    if app.status == "maintenance" or app.status == "paused":
        app.status = "enabled"
        msg = f"🟢 Application '{app.name}' is now ONLINE & OPERATIONAL."
        log_audit(db, app.id, "MAINTENANCE_OFF", details=f"Maintenance mode deactivated by {dev.username}", status="SUCCESS")
    else:
        app.status = "maintenance"
        msg = f"🚨 EMERGENCY MAINTENANCE MODE ACTIVATED for '{app.name}'. All client .exe executables are forcefully blocked."
        log_audit(db, app.id, "MAINTENANCE_ON", details=f"Maintenance mode activated by {dev.username}", status="DANGER")
    
    db.commit()
    return {"success": True, "message": msg, "new_status": app.status}

# ==================== IN-APP CLIENT NOTIFICATIONS ====================
@router.get("/notifications")
async def list_notifications(app_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    notifs = db.query(AppNotification).filter(AppNotification.app_id == app_id).order_by(AppNotification.created_at.desc()).all()
    return {
        "success": True,
        "notifications": [
            {
                "id": n.id,
                "app_id": n.app_id,
                "title": n.title,
                "message": n.message,
                "type": n.type,
                "is_active": n.is_active,
                "show_on_login": n.show_on_login,
                "created_at": n.created_at.isoformat()
            }
            for n in notifs
        ]
    }

@router.post("/notifications")
async def create_notification(data: CreateNotificationRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == dev.id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    title = data.title.strip()
    message = data.message.strip()
    if not title or not message:
        raise HTTPException(status_code=400, detail="Title and message are required")
    
    notif = AppNotification(
        app_id=data.app_id,
        title=title,
        message=message,
        type=data.type or "info",
        is_active=True,
        show_on_login=data.show_on_login if data.show_on_login is not None else True
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return {"success": True, "message": "Client Notification created successfully!", "notification_id": notif.id}

@router.delete("/notifications/{notif_id}")
async def delete_notification(notif_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    notif = db.query(AppNotification).join(Application).filter(AppNotification.id == notif_id, Application.developer_id == dev.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notif)
    db.commit()
    return {"success": True, "message": "Notification deleted successfully"}

@router.patch("/notifications/{notif_id}/toggle")
async def toggle_notification(notif_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    notif = db.query(AppNotification).join(Application).filter(AppNotification.id == notif_id, Application.developer_id == dev.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notif.is_active = not notif.is_active
    db.commit()
    status_label = "active" if notif.is_active else "disabled"
    return {"success": True, "message": f"Notification marked as {status_label}", "is_active": notif.is_active}

@router.put("/notifications/{notif_id}")
async def update_notification(notif_id: int, data: UpdateNotificationRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    notif = db.query(AppNotification).join(Application).filter(AppNotification.id == notif_id, Application.developer_id == dev.id).first()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    if data.title is not None:
        notif.title = data.title.strip()
    if data.message is not None:
        notif.message = data.message.strip()
    if data.type is not None:
        notif.type = data.type
    if data.show_on_login is not None:
        notif.show_on_login = data.show_on_login
    if data.is_active is not None:
        notif.is_active = data.is_active

    db.commit()
    return {"success": True, "message": "Broadcast notice updated successfully!"}

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
    
    count = min(max(1, data.amount or data.count), 500)

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
        while db.query(License).filter(License.app_id == data.app_id, License.license_key == raw_key).first():
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

    uname = data.username.strip()
    pwd = data.password.strip()
    is_same_key = (uname == pwd)

    new_user = User(
        app_id=data.app_id,
        username=uname,
        password_hash=hash_password(pwd),
        subscription_tier=data.subscription_tier or "default",
        level=data.level or 1,
        expires_at=expires_at,
        hwid=data.hwid.strip() if data.hwid else None,
        registered_ip="Manual Entry",
        key_used=uname if is_same_key else "Manual by Developer"
    )
    db.add(new_user)

    if is_same_key:
        global_lic = db.query(License).filter(License.license_key == uname).first()
        if not global_lic:
            new_lic = License(
                app_id=data.app_id,
                license_key=uname,
                duration_days=data.duration_days if data.duration_days > 0 else 99999,
                level=data.subscription_tier or "default",
                status="used",
                used_by_username=uname,
                used_at=datetime.datetime.utcnow(),
                notes=f"Universal Key Account (User=Pass) created by {dev.username}"
            )
            db.add(new_lic)
        elif global_lic.app_id == data.app_id:
            global_lic.status = "used"
            global_lic.used_by_username = uname

    db.commit()
    log_audit(db, app.id, "MANUAL_USER_CREATE", username=new_user.username, details="Created universal key/account" if is_same_key else "Created manually by developer", status="SUCCESS")
    
    return {
        "success": True,
        "message": f"Universal Key '{uname}' created successfully" if is_same_key else f"User '{new_user.username}' created successfully",
        "is_same_key": is_same_key,
        "key": uname,
        "username": uname,
        "password": pwd,
        "app_name": app.name,
        "subscription": new_user.subscription_tier,
        "duration_days": data.duration_days,
        "expires_at": new_user.expires_at.isoformat() if new_user.expires_at else "Lifetime"
    }

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
async def toggle_ban_user(user_id: int, data: Optional[BanUserRequest] = None, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    user = db.query(User).join(Application).filter(
        User.id == user_id,
        Application.developer_id == dev.id
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_banned = not user.is_banned
    if user.is_banned:
        user.ban_reason = (data.reason if data else None) or "Banned by developer"
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
        file_name=(data.file_name or data.file_id).strip(),
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
    
    balance_val = data.balance_credits if data.balance_credits is not None else (data.balance or 50)
    allowed_apps_val = str(data.app_id) if data.app_id else (data.allowed_apps or "all")

    reseller = Reseller(
        developer_id=dev.id,
        username=data.username.strip(),
        password_hash=hash_password(data.password),
        balance=balance_val,
        allowed_apps=allowed_apps_val
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

@router.patch("/resellers/{reseller_id}/apps")
async def update_reseller_apps(reseller_id: int, data: UpdateResellerAppsRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    
    reseller.allowed_apps = data.allowed_apps.strip() if data.allowed_apps else "all"
    db.commit()
    return {"success": True, "message": f"Updated assigned applications for reseller '{reseller.username}'", "allowed_apps": reseller.allowed_apps}

@router.post("/resellers/{reseller_id}/convert-to-client")
async def convert_reseller_to_client(reseller_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    reseller = db.query(Reseller).filter(Reseller.id == reseller_id, Reseller.developer_id == dev.id).first()
    if not reseller:
        raise HTTPException(status_code=404, detail="Reseller not found")
    
    uname = reseller.username
    existing_cc = db.query(CustomClient).filter(CustomClient.username == uname).first()
    if existing_cc:
        raise HTTPException(status_code=400, detail=f"A Custom Client account with username '{uname}' already exists.")
    
    new_cc = CustomClient(
        developer_id=dev.id,
        username=uname,
        password_hash=reseller.password_hash,
        allowed_apps=reseller.allowed_apps or "",
        notes=f"Converted from Reseller account (had {reseller.balance} credits)"
    )
    db.add(new_cc)
    db.delete(reseller)
    db.commit()
    db.refresh(new_cc)
    
    log_audit(db, None, "ROLE_CONVERT", username=uname, details=f"Reseller '{uname}' converted to Custom Client with full dashboard access", status="SUCCESS")
    return {"success": True, "message": f"Reseller '{uname}' successfully converted to Custom Client with full dashboard access!", "client_id": new_cc.id}

@router.post("/custom-clients/{client_id}/convert-to-reseller")
async def convert_client_to_reseller(client_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    cc = db.query(CustomClient).filter(CustomClient.id == client_id, CustomClient.developer_id == dev.id).first()
    if not cc:
        raise HTTPException(status_code=404, detail="Custom Client account not found")
    
    uname = cc.username
    existing_reseller = db.query(Reseller).filter(Reseller.username == uname).first()
    if existing_reseller:
        raise HTTPException(status_code=400, detail=f"A Reseller account with username '{uname}' already exists.")
    
    new_reseller = Reseller(
        developer_id=dev.id,
        username=uname,
        password_hash=cc.password_hash,
        balance=100,
        allowed_apps=cc.allowed_apps or "all"
    )
    db.add(new_reseller)
    db.delete(cc)
    db.commit()
    db.refresh(new_reseller)
    
    log_audit(db, None, "ROLE_CONVERT", username=uname, details=f"Custom Client '{uname}' converted to Reseller with 100 credits", status="SUCCESS")
    return {"success": True, "message": f"Custom Client '{uname}' successfully converted to Reseller with 100 key credits!", "reseller_id": new_reseller.id}

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


# ==================== UNIVERSAL DISCORD BOT DEVELOPER & STAFF RESOLVER ====================
def resolve_bot_developer(
    db: Session,
    discord_id: Optional[str] = None,
    discord_username: Optional[str] = None,
    guild_id: Optional[str] = None,
    guild_owner_id: Optional[str] = None,
    is_staff: Optional[bool] = False
) -> Optional[Developer]:
    """Resolves developer workspace by direct link, staff role inheritance, guild owner, custom client, or master admin."""
    d_id = str(discord_id).strip() if discord_id else ""
    d_user = str(discord_username).strip() if discord_username else ""
    g_owner = str(guild_owner_id).strip() if guild_owner_id else ""

    dev = None
    # 0. Check if this is a Custom Client (Brand Partner)
    client = None
    if d_id:
        client = db.query(CustomClient).filter(CustomClient.discord_id == d_id).first()
    if not client and d_user:
        client = db.query(CustomClient).filter(CustomClient.username.ilike(d_user)).first()
    if client:
        dev = db.query(Developer).filter(Developer.id == client.developer_id).first()
        if dev:
            dev.is_custom_client = True
            dev.custom_client_id = client.id
            dev.custom_client_username = client.username
            dev.allowed_apps_raw = client.allowed_apps or ""
            dev.allowed_apps_list = [x.strip() for x in (client.allowed_apps or "").split(",") if x.strip()]
            return dev

    # 1. Direct personal Discord ID link
    if d_id:
        dev = db.query(Developer).filter(Developer.discord_id == d_id).first()

    # 2. Direct username / email match
    if not dev and d_user:
        dev = db.query(Developer).filter(Developer.username.ilike(d_user)).first()
    if not dev and d_user:
        dev = db.query(Developer).filter(Developer.email.ilike(f"{d_user}%")).first()

    # 3. Staff Role Inheritance: Resolve Guild Owner's developer account
    if not dev and is_staff and g_owner:
        dev = db.query(Developer).filter(Developer.discord_id == g_owner).first()

    # 4. Staff Role Fallback: Resolve Master Admin / Server Workspace
    if not dev and is_staff:
        from ..config import MASTER_ADMIN_IDS
        dev = db.query(Developer).filter(Developer.discord_id.in_(MASTER_ADMIN_IDS)).first()
        if not dev:
            dev = db.query(Developer).filter(Developer.plan.in_(["Paid", "Developer", "Enterprise"])).first()

    # 5. Master Admin Direct Fallback
    if not dev and d_id:
        from ..config import MASTER_ADMIN_IDS
        if d_id in MASTER_ADMIN_IDS:
            dev = db.query(Developer).order_by(Developer.id.asc()).first()

    return dev

# ==================== DISCORD BOT AUTO-FETCH API ====================
class BotGenKeyRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    count: int = 1
    duration_days: int = 30
    level: str = "default"
    mask: str = "JOYST-XXXX-XXXX-XXXX"
    custom_key: Optional[str] = None
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/genkey")
async def bot_auto_genkey(data: BotGenKeyRequest, db: Session = Depends(get_db)):
    """Auto-detects developer by Discord ID and generates licenses instantly."""
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))

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

    created_keys = []
    custom_k = data.custom_key.strip() if data.custom_key else None
    if custom_k:
        existing_lic = db.query(License).filter(License.app_id == app.id, License.license_key == custom_k).first()
        if existing_lic:
            raise HTTPException(status_code=400, detail=f"License key '{custom_k}' already exists in application '{app.name}'.")
        
        lic = License(
            app_id=app.id,
            license_key=custom_k,
            duration_days=data.duration_days,
            level=data.level,
            level_rank=1,
            notes=f"Custom key created via Discord Bot for {data.discord_username or dev.username}"
        )
        db.add(lic)
        created_keys.append(custom_k)
    else:
        count = min(max(1, data.count), 50)
        for _ in range(count):
            k = generate_license_key(data.mask)
            while db.query(License).filter(License.app_id == app.id, License.license_key == k).first():
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
    """Allows Google, Username developers, or Custom Clients to link their Discord ID to their account in 1-click."""
    ident = data.email_or_username.strip()
    discord_id_clean = str(data.discord_id).strip()

    # 1. Try finding Developer
    dev = db.query(Developer).filter(
        (Developer.email.ilike(ident)) |
        (Developer.username.ilike(ident)) |
        (Developer.owner_id == ident)
    ).first()

    if dev:
        dev.discord_id = discord_id_clean
        db.commit()
        return {
            "success": True,
            "message": f"Successfully linked Discord @{data.discord_username or data.discord_id} to Developer Account @{dev.username}!",
            "developer": dev.username,
            "email": dev.email or "Google Auth",
            "plan": dev.plan
        }

    # 2. Try finding Custom Client (Brand Partner)
    client = db.query(CustomClient).filter(CustomClient.username.ilike(ident)).first()
    if client:
        client.discord_id = discord_id_clean
        db.commit()
        return {
            "success": True,
            "message": f"Successfully linked Discord @{data.discord_username or data.discord_id} to Brand Partner Account @{client.username}!",
            "developer": client.username,
            "email": "Brand Partner",
            "plan": "Enterprise"
        }

    raise HTTPException(status_code=404, detail=f"No account found matching '{ident}'. Make sure you entered your correct Dashboard username.")

class BotCreateUserRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    username: str
    password: str
    duration_days: int = 30
    subscription_tier: Optional[str] = "default"
    level: Optional[int] = 1
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/adduser")
async def bot_add_user(data: BotCreateUserRequest, db: Session = Depends(get_db)):
    """Create user and password directly via Discord Bot."""
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
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

    uname = data.username.strip()
    pwd = data.password.strip()
    is_same_key = (uname == pwd)

    new_user = User(
        app_id=app.id,
        username=uname,
        password_hash=hash_password(pwd),
        subscription_tier=data.subscription_tier or "default",
        level=data.level or 1,
        expires_at=expires_at,
        registered_ip="Discord Bot",
        key_used=uname if is_same_key else "Manual by Discord Bot"
    )
    db.add(new_user)

    if is_same_key:
        lic_existing = db.query(License).filter(License.app_id == app.id, License.license_key == uname).first()
        if not lic_existing:
            try:
                new_lic = License(
                    app_id=app.id,
                    license_key=uname,
                    duration_days=data.duration_days if data.duration_days > 0 else 99999,
                    level=data.subscription_tier or "default",
                    status="used",
                    used_by_username=uname,
                    used_at=datetime.datetime.utcnow(),
                    notes=f"Universal Key (User=Pass) created via Bot by @{data.discord_username or dev.username}"
                )
                db.add(new_lic)
            except Exception as e:
                print(f"[BOT UNIVERSAL KEY NOTICE] {e}")
        else:
            if lic_existing.app_id == app.id:
                lic_existing.status = "used"
                lic_existing.used_by_username = uname

    db.commit()
    db.refresh(new_user)

    log_audit(db, app.id, "MANUAL_USER_CREATE", username=new_user.username, details=f"Created universal key/user via Discord Bot by @{data.discord_username or dev.username}" if is_same_key else f"Created via Discord Bot by @{data.discord_username or dev.username}", status="SUCCESS")

    return {
        "success": True,
        "message": f"Universal key '{uname}' provisioned." if is_same_key else f"Client user '{new_user.username}' created successfully.",
        "is_same_key": is_same_key,
        "key": uname,
        "username": uname,
        "password": pwd,
        "app_name": app.name,
        "duration_days": data.duration_days,
        "subscription": new_user.subscription_tier,
        "expires_at": new_user.expires_at.strftime("%Y-%m-%d %H:%M UTC") if new_user.expires_at else "Lifetime"
    }

class BotUserActionRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    target_username: Optional[str] = None
    username: Optional[str] = None
    reason: Optional[str] = "Admin action via Discord Bot"
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/resethwid")
async def bot_reset_hwid(data: BotUserActionRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = (data.target_username or data.username or "").strip()
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
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = (data.target_username or data.username or "").strip()
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
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = (data.target_username or data.username or "").strip()
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
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    target = (data.target_username or data.username or "").strip()
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
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/stats")
async def bot_get_stats(data: BotStatsRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
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

@router.post("/bot/apps")
async def bot_get_developer_apps(data: BotStatsRequest, db: Session = Depends(get_db)):
    """Returns all applications owned by developer for Discord Dropdown Menus."""
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature. Please upgrade your plan on joystauth.cc to unlock Discord Bot access!")

    apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    return {
        "success": True,
        "developer": dev.username,
        "apps": [{"id": a.id, "name": a.name, "version": a.version, "secret": a.secret} for a in apps]
    }

class BotAddResellerRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    reseller_username: str
    reseller_password: str
    balance: int = 50
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/addreseller")
async def bot_create_reseller(data: BotAddResellerRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature.")

    u_name = data.reseller_username.strip()
    existing = db.query(Reseller).filter(Reseller.developer_id == dev.id, Reseller.username == u_name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Reseller '{u_name}' already exists in your workspace.")

    new_reseller = Reseller(
        developer_id=dev.id,
        username=u_name,
        password_hash=hash_password(data.reseller_password),
        balance=max(0, data.balance),
        is_active=True,
        allowed_apps="*"
    )
    db.add(new_reseller)
    db.commit()
    db.refresh(new_reseller)

    log_audit(db, None, "ADD_RESELLER", details=f"Reseller @{new_reseller.username} created via Discord Bot by @{data.discord_username or dev.username} with {new_reseller.balance} credits", status="SUCCESS")

    return {
        "success": True,
        "reseller_username": new_reseller.username,
        "balance": new_reseller.balance,
        "developer": dev.username
    }

class BotAddBalanceRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    reseller_username: str
    amount: int = 20
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/addbalance")
async def bot_add_reseller_balance(data: BotAddBalanceRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    if dev.plan != "Paid" and dev.plan != "Developer" and dev.plan != "Enterprise":
        raise HTTPException(status_code=403, detail="💎 Discord Bot integration is an exclusive PAID Plan feature.")

    u_name = data.reseller_username.strip()
    reseller = db.query(Reseller).filter(Reseller.developer_id == dev.id, Reseller.username == u_name).first()
    if not reseller:
        raise HTTPException(status_code=404, detail=f"Reseller '{u_name}' not found.")

    reseller.balance += data.amount
    db.commit()

    return {
        "success": True,
        "reseller_username": reseller.username,
        "added_amount": data.amount,
        "new_balance": reseller.balance
    }

class BotResellerInfoRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    reseller_username: str
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/resellerinfo")
async def bot_get_reseller_info(data: BotResellerInfoRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    u_name = data.reseller_username.strip()
    reseller = db.query(Reseller).filter(Reseller.developer_id == dev.id, Reseller.username == u_name).first()
    if not reseller:
        raise HTTPException(status_code=404, detail=f"Reseller '{u_name}' not found.")

    return {
        "success": True,
        "reseller": {
            "id": reseller.id,
            "username": reseller.username,
            "balance": reseller.balance,
            "is_active": reseller.is_active,
            "allowed_apps": reseller.allowed_apps or "All Apps",
            "created_at": reseller.created_at.isoformat() if reseller.created_at else "Unknown"
        }
    }

class BotRedeemRequest(BaseModel):
    discord_id: str
    discord_username: str
    license_key: str

@router.post("/bot/redeem")
async def bot_redeem_license_key(data: BotRedeemRequest, db: Session = Depends(get_db)):
    """Customer License Key Redemption on Discord to auto-assign role and activate subscription."""
    raw_key = data.license_key.strip().upper()
    lic = db.query(License).filter(License.license_key == raw_key).first()
    if not lic:
        raise HTTPException(status_code=404, detail="Invalid license key. Please verify and try again.")

    if lic.status != "unused":
        raise HTTPException(status_code=400, detail=f"This license key has already been used (Status: {lic.status}).")

    app = db.query(Application).filter(Application.id == lic.app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Associated application not found.")

    # Check if a user with this discord_id already exists in this app
    u_name = data.discord_username.strip()
    user = db.query(User).filter(User.app_id == app.id, (User.discord_id == data.discord_id) | (User.username == u_name)).first()

    now = datetime.datetime.utcnow()
    duration = lic.duration_days

    if user:
        # Extend subscription
        if duration == -1:
            user.expires_at = None # Lifetime
        else:
            base_time = user.expires_at if (user.expires_at and user.expires_at > now) else now
            user.expires_at = base_time + datetime.timedelta(days=duration)
        user.subscription_tier = lic.level
        user.level = lic.level_rank
        user.discord_id = str(data.discord_id)
    else:
        # Create new user for customer
        expires_at = None if duration == -1 else (now + datetime.timedelta(days=duration))
        user = User(
            app_id=app.id,
            username=u_name,
            password_hash=hash_password(generate_random_token(16)),
            subscription_tier=lic.level,
            level=lic.level_rank,
            expires_at=expires_at,
            registered_ip="Discord Redeem",
            key_used=lic.license_key,
            discord_id=str(data.discord_id)
        )
        db.add(user)

    # Mark key as used
    lic.status = "used"
    lic.used_by = user.username
    lic.used_at = now
    db.commit()
    db.refresh(user)

    log_audit(db, app.id, "LICENSE_REDEEM", username=user.username, details=f"License {lic.license_key} redeemed via Discord by @{data.discord_username}", status="SUCCESS")

    return {
        "success": True,
        "message": "License redeemed successfully!",
        "username": user.username,
        "app_name": app.name,
        "duration_days": duration,
        "rank": user.subscription_tier,
        "expires_at": user.expires_at.strftime("%Y-%m-%d %H:%M UTC") if user.expires_at else "Lifetime"
    }

class BotGenPlanKeyRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    count: int = 1
    plan: Optional[str] = "Paid"


class BotGlobalStatsRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""

@router.post("/bot/globalstats")
async def bot_get_global_platform_stats(data: BotGlobalStatsRequest, db: Session = Depends(get_db)):
    """Returns platform-wide master telemetry for Platform Owners (Master Admin Only)."""
    master_admins = ["956388318961086465", "1307214230134591559"]
    d_id = str(data.discord_id).strip()
    if d_id not in master_admins:
        raise HTTPException(status_code=403, detail="Platform Master Admin authorization required.")

    tot_devs = db.query(Developer).count()
    tot_apps = db.query(Application).count()
    tot_users = db.query(User).count()
    tot_keys = db.query(License).count()
    unused_keys = db.query(License).filter(License.status == "unused").count()
    used_keys = db.query(License).filter(License.status == "used").count()
    tot_resellers = db.query(Reseller).count()
    tot_blacklists = db.query(Blacklist).count()

    recent_devs = db.query(Developer).order_by(Developer.id.desc()).limit(5).all()
    recent_list = [f"@{d.username} ({d.email or 'No email'}) • {d.plan}" for d in recent_devs]

    return {
        "success": True,
        "total_developers": tot_devs,
        "total_applications": tot_apps,
        "total_clients": tot_users,
        "total_keys": tot_keys,
        "unused_keys": unused_keys,
        "used_keys": used_keys,
        "total_resellers": tot_resellers,
        "total_blacklists": tot_blacklists,
        "recent_developers": recent_list
    }

@router.post("/bot/genplankey")
async def bot_gen_plan_upgrade_keys(data: BotGenPlanKeyRequest, db: Session = Depends(get_db)):
    """Generate VIP / Paid Developer Plan Upgrade Keys from Discord Bot."""
    from ..database import PlanKey
    count = min(max(1, data.count), 20)
    created_keys = []
    for _ in range(count):
        code = "JOYST-PAID-" + generate_random_token(4).upper() + "-" + generate_random_token(4).upper() + "-" + generate_random_token(4).upper()
        p = PlanKey(key_code=code, target_plan=data.plan or "Paid", is_used=False)
        db.add(p)
        created_keys.append(code)
    db.commit()

    return {
        "success": True,
        "keys": created_keys,
        "count": len(created_keys),
        "plan": data.plan or "Paid"
    }

class BotUpgradePlanRequest(BaseModel):
    discord_id: str
    discord_username: str
    plan_key: str

@router.post("/bot/upgradeplan")
async def bot_upgrade_developer_plan(data: BotUpgradePlanRequest, db: Session = Depends(get_db)):
    """Redeem a Plan Key on Discord to instantly upgrade Developer Account from Free to Paid."""
    from ..database import PlanKey
    raw_key = data.plan_key.strip().upper()
    p_key = db.query(PlanKey).filter(PlanKey.key_code == raw_key, PlanKey.is_used == False).first()

    # Allow master override keys as well
    is_valid_master = raw_key.startswith("JOYST-PAID-") or raw_key.startswith("JOYST-PRO-") or raw_key.startswith("JOYST-DEV-") or raw_key.startswith("JOYST-ENT-") or raw_key == "PAID-UPGRADE-2026" or raw_key == "DEV-UPGRADE-2026" or raw_key == "ENT-UPGRADE-2026"

    if not p_key and not is_valid_master:
        raise HTTPException(status_code=400, detail="Invalid or already used Plan Upgrade Key.")

    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    dev.plan = "Paid"
    dev.max_apps = 999999
    dev.max_users_per_app = 999999

    if p_key:
        p_key.is_used = True
        p_key.used_by_username = dev.username

    db.commit()
    db.refresh(dev)

    return {
        "success": True,
        "message": "Developer Account upgraded to PAID Plan successfully!",
        "developer": dev.username,
        "plan": dev.plan,
        "max_apps": dev.max_apps,
        "max_users": dev.max_users_per_app
    }

class BotMaintenanceRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    state: Optional[str] = "toggle" # "enable", "disable", "toggle"
    message: Optional[str] = None
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/maintenance")
async def bot_toggle_maintenance(data: BotMaintenanceRequest, db: Session = Depends(get_db)):
    """Toggle Maintenance Mode for an application directly via Discord Bot."""
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    app = None
    if data.app_name:
        app = db.query(Application).filter(Application.developer_id == dev.id, Application.name.ilike(data.app_name)).first()
    if not app:
        app = db.query(Application).filter(Application.developer_id == dev.id).first()

    if not app:
        raise HTTPException(status_code=404, detail="No application found.")

    if data.state == "enable":
        app.status = "maintenance"
    elif data.state == "disable":
        app.status = "enabled"
    else:
        app.status = "enabled" if app.status == "maintenance" or app.status == "paused" else "maintenance"

    if data.message:
        app.maintenance_message = data.message.strip()

    db.commit()
    is_maint = app.status in ["maintenance", "paused"]
    status_label = "🔴 MAINTENANCE (ALL EXEs BLOCKED)" if is_maint else "🟢 ONLINE & OPERATIONAL"

    log_audit(db, app.id, "MAINTENANCE_TOGGLE", details=f"Maintenance mode set to '{app.status}' via Discord by @{data.discord_username}", status="DANGER" if is_maint else "SUCCESS")

    return {
        "success": True,
        "app_name": app.name,
        "status": app.status,
        "status_label": status_label,
        "is_maintenance": is_maint,
        "maintenance_message": app.maintenance_message or "Application is currently under maintenance."
    }

class BotWarningRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    title: str
    message: str
    type: Optional[str] = "danger" # danger, warning, info, success
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/warning")
async def bot_broadcast_warning(data: BotWarningRequest, db: Session = Depends(get_db)):
    """Broadcast an Emergency Warning / Notice to all client .exe software from Discord."""
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found. Run `/link [email_or_username]` first.")

    app = None
    if data.app_name:
        app = db.query(Application).filter(Application.developer_id == dev.id, Application.name.ilike(data.app_name)).first()
    if not app:
        app = db.query(Application).filter(Application.developer_id == dev.id).first()

    if not app:
        raise HTTPException(status_code=404, detail="No application found.")

    notif = AppNotification(
        app_id=app.id,
        title=data.title.strip(),
        message=data.message.strip(),
        type=data.type or "danger",
        is_active=True,
        show_on_login=True
    )
    db.add(notif)
    db.commit()

    log_audit(db, app.id, "WARNING_BROADCAST", details=f"Live warning '{data.title}' broadcasted via Discord by @{data.discord_username}", status="DANGER" if data.type == "danger" else "WARNING")

    return {
        "success": True,
        "message": "Live Warning Broadcasted to all .exe clients!",
        "app_name": app.name,
        "title": notif.title,
        "type": notif.type,
        "notification_id": notif.id
    }


# ==================== BOT DELETE & LIST ENDPOINTS ====================
class BotDeleteUserRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    target_username: str
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/deluser")
async def bot_delete_user(data: BotDeleteUserRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found.")

    apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    app_ids = [a.id for a in apps]
    if not app_ids:
        raise HTTPException(status_code=404, detail="No applications found.")

    u = db.query(User).filter(User.app_id.in_(app_ids), User.username.ilike(data.target_username.strip())).first()
    if not u:
        raise HTTPException(status_code=404, detail=f"User '{data.target_username}' not found.")

    uname = u.username
    app_id = u.app_id
    db.delete(u)
    db.commit()
    log_audit(db, app_id, "USER_DELETED", details=f"Client user '{uname}' deleted via Discord by @{data.discord_username}", status="DANGER")

    return {
        "success": True,
        "message": f"Client user '{uname}' permanently deleted.",
        "username": uname
    }

class BotDeleteKeyRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    target_key: str
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/delkey")
async def bot_delete_key(data: BotDeleteKeyRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found.")

    apps = db.query(Application).filter(Application.developer_id == dev.id).all()
    app_ids = [a.id for a in apps]
    if not app_ids:
        raise HTTPException(status_code=404, detail="No applications found.")

    lic = db.query(License).filter(License.app_id.in_(app_ids), License.license_key == data.target_key.strip()).first()
    if not lic:
        raise HTTPException(status_code=404, detail=f"License key '{data.target_key}' not found.")

    k = lic.license_key
    app_id = lic.app_id
    db.delete(lic)
    db.commit()
    log_audit(db, app_id, "KEY_DELETED", details=f"License key '{k}' deleted via Discord by @{data.discord_username}", status="DANGER")

    return {
        "success": True,
        "message": f"License key '{k}' permanently deleted.",
        "key": k
    }

class BotListUsersRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    limit: Optional[int] = 15
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/listusers")
async def bot_list_users(data: BotListUsersRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found.")

    query = db.query(User).join(Application).filter(Application.developer_id == dev.id)
    if data.app_name:
        query = query.filter(Application.name.ilike(data.app_name.strip()))

    total = query.count()
    users = query.order_by(desc(User.id)).limit(min(max(1, data.limit or 15), 50)).all()

    return {
        "success": True,
        "total": total,
        "users": [
            {
                "id": u.id,
                "username": u.username,
                "subscription": u.subscription,
                "expires_at": u.expires_at.strftime("%Y-%m-%d %H:%M") if u.expires_at else "Lifetime",
                "is_banned": u.is_banned,
                "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "Never",
                "hwid_locked": bool(u.hwid)
            }
            for u in users
        ]
    }

class BotListKeysRequest(BaseModel):
    discord_id: str
    discord_username: Optional[str] = ""
    app_name: Optional[str] = None
    status_filter: Optional[str] = None # unused, used, all
    limit: Optional[int] = 15
    guild_id: Optional[str] = None
    guild_owner_id: Optional[str] = None
    is_staff: Optional[bool] = False

@router.post("/bot/listkeys")
async def bot_list_keys(data: BotListKeysRequest, db: Session = Depends(get_db)):
    dev = resolve_bot_developer(db, data.discord_id, data.discord_username, getattr(data, "guild_id", None), getattr(data, "guild_owner_id", None), getattr(data, "is_staff", False))
    if not dev:
        raise HTTPException(status_code=404, detail="No linked Developer account found.")

    query = db.query(License).join(Application).filter(Application.developer_id == dev.id)
    if data.app_name:
        query = query.filter(Application.name.ilike(data.app_name.strip()))
    if data.status_filter and data.status_filter != "all":
        query = query.filter(License.status == data.status_filter.lower())

    total = query.count()
    unused_count = db.query(License).join(Application).filter(Application.developer_id == dev.id, License.status == "unused").count()
    used_count = db.query(License).join(Application).filter(Application.developer_id == dev.id, License.status == "used").count()

    keys = query.order_by(desc(License.id)).limit(min(max(1, data.limit or 15), 50)).all()

    return {
        "success": True,
        "total": total,
        "unused_count": unused_count,
        "used_count": used_count,
        "keys": [
            {
                "key": k.license_key,
                "duration_days": k.duration_days,
                "level": k.level,
                "status": k.status,
                "used_by": k.used_by_username or "None"
            }
            for k in keys
        ]
    }


class ChangelogCreateRequest(BaseModel):
    version: str
    title: str
    category: Optional[str] = "Feature"
    description: str

@router.post("/changelog")
def publish_changelog_entry(data: ChangelogCreateRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    """Publish a new system release note / update entry to the live website timeline."""
    from .auth_api import is_master_admin_account
    if not is_master_admin_account(dev):
        raise HTTPException(status_code=403, detail="Access Denied: Only Joyst Platform Master Owner can publish global website updates.")
    from ..database import ChangelogEntry
    entry = ChangelogEntry(
        version=data.version.strip(),
        title=data.title.strip(),
        category=data.category.strip() if data.category else "Feature",
        description=data.description.strip(),
        author=dev.username
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {"success": True, "message": "Changelog entry published live to website!", "entry_id": entry.id}


@router.delete("/changelog/{entry_id}")
def delete_changelog_entry(entry_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    """Delete a changelog update entry from live website."""
    from .auth_api import is_master_admin_account
    if not is_master_admin_account(dev):
        raise HTTPException(status_code=403, detail="Access Denied: Only Joyst Platform Master Owner can delete global website updates.")
    from ..database import ChangelogEntry
    entry = db.query(ChangelogEntry).filter(ChangelogEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Changelog entry not found")
    db.delete(entry)
    db.commit()
    return {"success": True, "message": "Changelog entry deleted successfully"}

# ==================== 15. CUSTOM CLIENTS / SUB-DEVELOPER MANAGEMENT ====================

@router.get("/custom-clients")
async def list_custom_clients(dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    clients = db.query(CustomClient).filter(CustomClient.developer_id == dev.id).order_by(CustomClient.id.desc()).all()
    all_dev_apps = {a.id: a.name for a in db.query(Application).filter(Application.developer_id == dev.id).all()}
    
    result = []
    for c in clients:
        allowed_raw = [x.strip() for x in (c.allowed_apps or "").split(",") if x.strip()]
        app_names = []
        for item in allowed_raw:
            if item.isdigit() and int(item) in all_dev_apps:
                app_names.append(all_dev_apps[int(item)])
            elif item in all_dev_apps.values():
                app_names.append(item)
            elif item == "all":
                app_names.append("All Applications")

        result.append({
            "id": c.id,
            "username": c.username,
            "allowed_apps": c.allowed_apps or "",
            "assigned_app_names": app_names,
            "notes": c.notes or "",
            "created_at": c.created_at.isoformat() if c.created_at else None
        })
    return {"success": True, "clients": result}

@router.post("/custom-clients")
async def create_custom_client(data: CreateCustomClientRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    uname = data.username.strip()
    if not uname:
        raise HTTPException(status_code=400, detail="Username is required")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Check duplicate username across Developers, Resellers, and CustomClients
    if db.query(Developer).filter(Developer.username == uname).first():
        raise HTTPException(status_code=400, detail=f"Username '{uname}' is already taken.")
    if db.query(Reseller).filter(Reseller.username == uname).first():
        raise HTTPException(status_code=400, detail=f"Username '{uname}' is already taken by a reseller.")
    if db.query(CustomClient).filter(CustomClient.username == uname).first():
        raise HTTPException(status_code=400, detail=f"Username '{uname}' is already registered as a custom client.")
    
    new_client = CustomClient(
        developer_id=dev.id,
        username=uname,
        password_hash=hash_password(data.password),
        allowed_apps=data.allowed_apps.strip(),
        notes=data.notes.strip() if data.notes else ""
    )
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    
    log_audit(db, None, "CLIENT_CREATED", username=uname, details=f"Custom client account created for apps: {new_client.allowed_apps}", status="SUCCESS")
    return {"success": True, "message": f"Custom client '{uname}' created successfully!", "client_id": new_client.id}

@router.put("/custom-clients/{client_id}")
async def update_custom_client(client_id: int, data: UpdateCustomClientRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    client = db.query(CustomClient).filter(CustomClient.id == client_id, CustomClient.developer_id == dev.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Custom client account not found")
    
    if data.password is not None and len(data.password.strip()) >= 6:
        client.password_hash = hash_password(data.password.strip())
    
    if data.allowed_apps is not None:
        client.allowed_apps = data.allowed_apps.strip()
        
    if data.notes is not None:
        client.notes = data.notes.strip()
        
    db.commit()
    return {"success": True, "message": f"Custom client '{client.username}' updated successfully!"}

@router.delete("/custom-clients/{client_id}")
async def delete_custom_client(client_id: int, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    client = db.query(CustomClient).filter(CustomClient.id == client_id, CustomClient.developer_id == dev.id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Custom client account not found")
    
    uname = client.username
    db.delete(client)
    db.commit()
    
    log_audit(db, None, "CLIENT_DELETED", username=uname, details=f"Custom client account '{uname}' deleted", status="WARNING")
    return {"success": True, "message": f"Custom client '{uname}' deleted permanently."}
