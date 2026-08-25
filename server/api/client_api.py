import json
import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db, Application, User, License, AppVariable, AppFile, Blacklist, Session as UserSession
from ..security import (
    aes_encrypt, aes_decrypt, compute_hmac_signature,
    verify_hmac_signature, generate_random_token,
    normalize_hwid, hash_password, verify_password
)
from ..config import log_audit

router = APIRouter(prefix="/api/v1/client", tags=["Joyst Corporation Client SDK API"])

@router.api_route("/health", methods=["GET", "HEAD"])
async def client_health_check():
    return {"status": "online", "version": "2.0.0", "service": "Joyst Auth Server"}

# In-memory fast brute force attempt tracker: (app_id, ip) or (app_id, hwid) -> {"count": int, "attempts": list, "last_seen": datetime}
failed_attempts_tracker = {}
MAX_FAILED_ATTEMPTS = 7

def check_and_record_failure(db: Session, app_id: int, app_name: str, ip: str, hwid: str, attempted_input: str, reason: str):
    """
    Tracks invalid username/password/license attempts.
    If 7th attempt is reached, automatically BAN the HWID & IP in Blacklists,
    record an audit log, and send a rich Discord webhook alert.
    """
    key = f"{app_id}_{hwid}" if hwid else f"{app_id}_{ip}"
    now = datetime.datetime.utcnow()

    if key not in failed_attempts_tracker:
        failed_attempts_tracker[key] = {
            "count": 0,
            "attempts": [],
            "first_seen": now,
            "last_seen": now
        }

    tracker = failed_attempts_tracker[key]
    
    # Reset count if last attempt was more than 30 minutes ago
    if (now - tracker["last_seen"]).total_seconds() > 1800:
        tracker["count"] = 0
        tracker["attempts"] = []

    tracker["count"] += 1
    tracker["last_seen"] = now
    if len(tracker["attempts"]) < 10:
        tracker["attempts"].append(f"{attempted_input} ({reason})")

    current_count = tracker["count"]

    if current_count >= MAX_FAILED_ATTEMPTS:
        # Auto Blacklist HWID and IP permanently
        try:
            if hwid:
                existing_hwid_bl = db.query(Blacklist).filter(Blacklist.app_id == app_id, Blacklist.type == "hwid", Blacklist.data == hwid).first()
                if not existing_hwid_bl:
                    bl_hwid = Blacklist(
                        app_id=app_id,
                        type="hwid",
                        data=hwid,
                        reason=f"Auto-Banned: Exceeded {MAX_FAILED_ATTEMPTS} brute force attempts"
                    )
                    db.add(bl_hwid)

            if ip and ip != "127.0.0.1":
                existing_ip_bl = db.query(Blacklist).filter(Blacklist.app_id == app_id, Blacklist.type == "ip", Blacklist.data == ip).first()
                if not existing_ip_bl:
                    bl_ip = Blacklist(
                        app_id=app_id,
                        type="ip",
                        data=ip,
                        reason=f"Auto-Banned: Exceeded {MAX_FAILED_ATTEMPTS} brute force attempts"
                    )
                    db.add(bl_ip)

            # If an existing user matches, mark them banned too
            if attempted_input:
                user_match = db.query(User).filter(User.app_id == app_id, User.username == attempted_input).first()
                if user_match:
                    user_match.is_banned = True
                    user_match.ban_reason = f"Brute Force Security Auto-Ban ({MAX_FAILED_ATTEMPTS} invalid attempts)"

            db.commit()

            # Rich Discord Webhook Alert
            history_summary = " | ".join(tracker["attempts"][-5:])
            extra_info = {
                "🚨 Security Status": "**PERMANENTLY BANNED & BLACKLISTED**",
                "🔢 Failed Attempts": f"`{current_count} / {MAX_FAILED_ATTEMPTS}`",
                "⚠️ Block Reason": "Continuous invalid username/pass/key combinations (Brute Force / Guessing Attack)",
                "📜 Recent Inputs": f"`{history_summary}`"
            }

            log_audit(
                db,
                app_id=app_id,
                action="SECURITY_BAN",
                username=attempted_input,
                ip_address=ip,
                hwid=hwid,
                details=f"Intruder exceeded {MAX_FAILED_ATTEMPTS} failed attempts. Machine HWID & IP permanently blacklisted.",
                status="DANGER",
                extra_data=extra_info
            )
        except Exception as e:
            print(f"[SECURITY AUTO BAN ERROR] {e}")

        return True # Indicates banned
    return False

class InitRequest(BaseModel):
    app_token: Optional[str] = ""
    token: Optional[str] = ""     # Standard token parameter
    name: Optional[str] = ""      # App Name
    ownerid: Optional[str] = ""   # Legacy fallback
    secret: Optional[str] = ""    # Legacy fallback
    version: Optional[str] = "1.0"
    hwid: Optional[str] = ""

class EncryptedPayloadRequest(BaseModel):
    sessionid: str
    data: str
    signature: Optional[str] = ""

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

# ================= 1. INITIALIZE CLIENT SESSION =================
@router.post("/init")
async def client_init(data: InitRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    hwid = normalize_hwid(data.hwid)

    app = None
    app_token_input = (data.token or data.secret or data.app_token or "").strip()

    # 1. Check if direct app token was matched
    if app_token_input and not data.name:
        app = db.query(Application).filter(Application.secret == app_token_input).first()
        if not app:
            app = db.query(Application).filter(Application.owner_id == app_token_input).first()
    
    # 2. Check if name and token were provided
    if not app and data.name and data.name.strip():
        if app_token_input:
            app = db.query(Application).filter(
                Application.name == data.name.strip(),
                Application.secret == app_token_input
            ).first()

        if not app and data.ownerid and data.ownerid.strip():
            app = db.query(Application).filter(
                Application.name == data.name.strip(),
                Application.owner_id == data.ownerid.strip()
            ).first()

    if not app:
        return {"success": False, "message": "Application does not exist or invalid credentials provided."}

    # Check Blacklist at init
    if hwid:
        bl_hwid = db.query(Blacklist).filter(Blacklist.app_id == app.id, Blacklist.type == "hwid", Blacklist.data == hwid).first()
        if bl_hwid:
            msg = getattr(app, "blacklist_message", "") or "Access Denied! Your IP or Machine HWID has been blacklisted."
            return {"success": False, "message": f"{msg} ({bl_hwid.reason})"}

    if ip and ip != "127.0.0.1":
        bl_ip = db.query(Blacklist).filter(Blacklist.app_id == app.id, Blacklist.type == "ip", Blacklist.data == ip).first()
        if bl_ip:
            msg = getattr(app, "blacklist_message", "") or "Access Denied! Your IP or Machine HWID has been blacklisted."
            return {"success": False, "message": f"{msg} ({bl_ip.reason})"}

    if app.status == "disabled":
        msg = getattr(app, "maintenance_message", "") or "This application is currently disabled by administrator."
        return {"success": False, "message": msg, "is_maintenance": True}

    if app.status == "paused" or app.status == "maintenance":
        msg = getattr(app, "maintenance_message", "") or "Application is under maintenance. Please check back soon."
        return {"success": False, "message": msg, "is_maintenance": True}

    # Integrity / Hash Checking if enabled
    if getattr(app, "hash_check_enabled", False) and app.app_hash:
        client_hash = data.dict().get("hash") or request.headers.get("X-Client-Hash", "")
        if client_hash and client_hash.strip().lower() != app.app_hash.strip().lower():
            log_audit(db, app.id, "INTEGRITY_FAIL", ip_address=ip, hwid=hwid, details="Client executable hash mismatch / modified crack", status="DANGER")
            msg = getattr(app, "hash_mismatch_message", "") or "Executable integrity verification failed! Modified or cracked binary detected."
            return {"success": False, "message": msg}

    # Strict Version Enforcement Check
    if app.version and data.version and app.version.strip() != data.version.strip():
        log_audit(db, app.id, "VERSION_MISMATCH", ip_address=ip, hwid=hwid, details=f"Client v{data.version} blocked. Latest is v{app.version}", status="WARNING")
        msg = getattr(app, "version_mismatch_message", "") or f"Update required! Latest version is v{app.version}, your client is v{data.version}."
        return {
            "success": False,
            "message": msg,
            "new_version": app.version,
            "download_url": app.download_link or ""
        }

    # Fetch active in-app notifications
    from ..database import AppNotification
    notifs = db.query(AppNotification).filter(AppNotification.app_id == app.id, AppNotification.is_active == True).all()
    active_notifs = [
        {"id": n.id, "title": n.title, "message": n.message, "type": n.type, "show_on_login": n.show_on_login}
        for n in notifs
    ]

    # Generate dynamic session ID and AES-256 session encryption key
    session_id = "sess_" + generate_random_token(32)
    session_key = generate_random_token(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=app.session_timeout_minutes)

    new_session = UserSession(
        session_token=session_id,
        app_id=app.id,
        hwid=hwid,
        ip_address=ip,
        encryption_key=session_key,
        expires_at=expires_at,
        is_valid=True
    )
    db.add(new_session)
    db.commit()

    # Encrypt session key with App Secret
    encrypted_session_key = aes_encrypt(session_key, app.secret)

    log_audit(db, app.id, "INIT_SUCCESS", ip_address=ip, hwid=hwid, details="Client initialized session", status="SUCCESS")

    return {
        "success": True,
        "message": "Initialized successfully",
        "sessionid": session_id,
        "enckey": encrypted_session_key,
        "app_name": app.name,
        "app_version": app.version,
        "custom_status": getattr(app, "custom_status", "UNDETECTED") or "UNDETECTED",
        "hwid_lock_enabled": app.hwid_lock_enabled,
        "notifications": active_notifs
    }

# ================= 2. ENCRYPTED GATEWAY FOR ALL CLIENT ACTIONS =================
@router.post("/gateway")
async def client_gateway(req_data: EncryptedPayloadRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)

    # 1. Fetch Session
    session = db.query(UserSession).filter(
        UserSession.session_token == req_data.sessionid,
        UserSession.is_valid == True
    ).first()

    if not session:
        return {"success": False, "message": "Invalid or expired session. Please re-initialize client."}

    if datetime.datetime.utcnow() > session.expires_at:
        session.is_valid = False
        db.commit()
        return {"success": False, "message": "Session expired. Please re-initialize."}

    app = db.query(Application).filter(Application.id == session.app_id).first()
    if not app:
        return {"success": False, "message": "Application not found."}

    # 2. Decrypt payload using session AES key
    try:
        decrypted_json_str = aes_decrypt(req_data.data, session.encryption_key)
        if isinstance(decrypted_json_str, str):
            decrypted_json_str = decrypted_json_str.lstrip('\ufeff').strip()
        data = json.loads(decrypted_json_str)
    except Exception as e:
        return {"success": False, "message": f"Payload decryption failed: {str(e)}"}

    action = data.get("type") or data.get("action", "")
    hwid = normalize_hwid(data.get("hwid", session.hwid or ""))

    if not session.hwid and hwid:
        session.hwid = hwid
        db.commit()

    # Pre-check Blacklists
    if hwid:
        bl_hwid = db.query(Blacklist).filter(Blacklist.app_id == app.id, Blacklist.type == "hwid", Blacklist.data == hwid).first()
        if bl_hwid:
            return {"success": False, "message": f"Your machine is banned: {bl_hwid.reason}"}

    response_data = {}

    # ---------------- LOGIN (Username & Password) ----------------
    if action == "login":
        username = data.get("username", "").strip()
        password = data.get("password", "")

        user = db.query(User).filter(User.app_id == app.id, User.username == username).first()
        if not user:
            is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "User not found")
            if is_banned:
                bf_msg = getattr(app, "brute_force_ban_message", "") or "Too many invalid attempts! Your PC hardware and IP are permanently banned."
                response_data = {"success": False, "message": bf_msg}
            else:
                log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Username not found", status="WARNING")
                unf_msg = getattr(app, "user_not_found_message", "") or "Username does not exist."
                response_data = {"success": False, "message": unf_msg}

        elif user.is_banned:
            log_audit(db, app.id, "LOGIN_BLOCKED", username=username, ip_address=ip, hwid=hwid, details=f"Banned: {user.ban_reason}", status="DANGER")
            ban_prefix = getattr(app, "banned_user_message", "") or "Account is banned!"
            response_data = {"success": False, "message": f"{ban_prefix} Reason: {user.ban_reason or 'No reason provided'}"}

        elif not verify_password(password, user.password_hash or ""):
            is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "Incorrect password")
            if is_banned:
                bf_msg = getattr(app, "brute_force_ban_message", "") or "Too many invalid attempts! Your PC hardware and IP are permanently banned."
                response_data = {"success": False, "message": bf_msg}
            else:
                log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Incorrect password", status="WARNING")
                fail_msg = getattr(app, "login_failed_message", "") or "Invalid username or password."
                response_data = {"success": False, "message": fail_msg}

        else:
            if user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                log_audit(db, app.id, "LOGIN_EXPIRED", username=username, ip_address=ip, hwid=hwid, details="Subscription expired", status="WARNING")
                exp_msg = getattr(app, "expired_sub_message", "") or "Your subscription has expired! Please renew."
                response_data = {"success": False, "message": exp_msg}
            else:
                # HWID Check
                is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
                if not user.hwid:
                    user.hwid = hwid
                    db.commit()
                    log_audit(db, app.id, "HWID_BIND", username=username, ip_address=ip, hwid=hwid, details="Hardware bound on first login", status="SUCCESS")

                if is_hwid_locked and user.hwid and user.hwid != hwid:
                    log_audit(db, app.id, "HWID_MISMATCH", username=username, ip_address=ip, hwid=hwid, details="Hardware ID mismatch", status="DANGER")
                    mismatch_msg = getattr(app, "hwid_mismatch_message", "") or "HWID Mismatch! Your account is locked to another computer. Contact administrator to reset HWID."
                    response_data = {
                        "success": False,
                        "message": mismatch_msg
                    }
                else:
                    user.last_login = datetime.datetime.utcnow()
                    user.last_ip = ip
                    session.user_id = user.id
                    db.commit()

                    # Clear failed attempts on success
                    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
                    failed_attempts_tracker.pop(key, None)

                    log_audit(db, app.id, "LOGIN_SUCCESS", username=username, ip_address=ip, hwid=hwid, details="User successfully authenticated", status="SUCCESS")
                    
                    time_left_str = "Lifetime"
                    if user.expires_at:
                        diff = user.expires_at - datetime.datetime.utcnow()
                        time_left_str = f"{diff.days} days, {diff.seconds // 3600} hours"

                    # Active in-app notifications
                    from ..database import AppNotification
                    notifs = db.query(AppNotification).filter(AppNotification.app_id == app.id, AppNotification.is_active == True, AppNotification.show_on_login == True).all()
                    active_notifs = [
                        {"id": n.id, "title": n.title, "message": n.message, "type": n.type}
                        for n in notifs
                    ]

                    success_msg = getattr(app, "login_success_message", "") or f"Logged in successfully! Welcome {user.username}"

                    response_data = {
                        "success": True,
                        "message": success_msg,
                        "notifications": active_notifs,
                        "info": {
                            "username": user.username,
                            "subscription": user.subscription_tier,
                            "expiry": user.expires_at.isoformat() if user.expires_at else "Lifetime",
                            "timeleft": time_left_str,
                            "hwid": user.hwid,
                            "ip": ip,
                            "created_date": user.created_at.isoformat()
                        }
                    }

    # ---------------- REGISTER (Username, Password, License) ----------------
    elif action == "register":
        username = data.get("username", "").strip()
        password = data.get("password", "")
        license_key = data.get("key") or data.get("license_key", "").strip()

        if not username or not password or not license_key:
            response_data = {"success": False, "message": "Username, password, and license key are all required."}
        else:
            existing_user = db.query(User).filter(User.app_id == app.id, User.username == username).first()
            if existing_user:
                response_data = {"success": False, "message": "Username is already registered."}
            else:
                license_obj = db.query(License).filter(License.app_id == app.id, License.license_key == license_key).first()
                if not license_obj:
                    is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, f"RegKey:{license_key}", "Invalid register license key")
                    if is_banned:
                        bf_msg = getattr(app, "brute_force_ban_message", "") or "Too many invalid attempts! Your PC hardware and IP are permanently banned."
                        response_data = {"success": False, "message": bf_msg}
                    else:
                        log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"Invalid key provided: {license_key}", status="WARNING")
                        inv_key_msg = getattr(app, "invalid_license_message", "") or "Invalid license key."
                        response_data = {"success": False, "message": inv_key_msg}
                elif license_obj.status != "unused":
                    log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"License already {license_obj.status}", status="WARNING")
                    used_key_msg = getattr(app, "used_license_message", "") or f"This license key is already {license_obj.status}."
                    response_data = {"success": False, "message": used_key_msg}
                else:
                    expires_at = None
                    if license_obj.duration_days > 0 and license_obj.duration_days < 90000:
                        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=license_obj.duration_days)

                    new_user = User(
                        app_id=app.id,
                        username=username,
                        password_hash=hash_password(password),
                        hwid=hwid,
                        last_ip=ip,
                        registered_ip=ip,
                        subscription_tier=license_obj.level,
                        expires_at=expires_at,
                        key_used=license_key,
                        created_at=datetime.datetime.utcnow(),
                        last_login=datetime.datetime.utcnow()
                    )
                    db.add(new_user)

                    license_obj.status = "used"
                    license_obj.used_by_username = username
                    license_obj.used_at = datetime.datetime.utcnow()
                    db.commit()

                    session.user_id = new_user.id
                    db.commit()

                    # Clear failed attempts on success
                    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
                    failed_attempts_tracker.pop(key, None)

                    log_audit(db, app.id, "REGISTER_SUCCESS", username=username, ip_address=ip, hwid=hwid, details=f"Registered account with key {license_key}", status="SUCCESS")

                    reg_ok_msg = getattr(app, "register_success_message", "") or "Account created successfully! You are now logged in."

                    response_data = {
                        "success": True,
                        "message": reg_ok_msg,
                        "info": {
                            "username": new_user.username,
                            "subscription": new_user.subscription_tier,
                            "expiry": new_user.expires_at.isoformat() if new_user.expires_at else "Lifetime",
                            "hwid": new_user.hwid
                        }
                    }

    # ---------------- LICENSE ONLY LOGIN (KeyAuth License Login) ----------------
    elif action == "license":
        license_key = (data.get("key") or data.get("license_key", "")).strip()
        license_obj = db.query(License).filter(License.app_id == app.id, License.license_key == license_key).first()

        if not license_obj:
            is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, f"Key:{license_key}", "Invalid direct license key")
            if is_banned:
                bf_msg = getattr(app, "brute_force_ban_message", "") or "Too many invalid attempts! Your PC hardware and IP are permanently banned."
                response_data = {"success": False, "message": bf_msg}
            else:
                log_audit(db, app.id, "LICENSE_FAIL", ip_address=ip, hwid=hwid, details=f"Invalid key {license_key}", status="WARNING")
                inv_key_msg = getattr(app, "invalid_license_message", "") or "Invalid license key."
                response_data = {"success": False, "message": inv_key_msg}
        elif license_obj.status == "paused":
            paused_msg = getattr(app, "paused_license_message", "") or "This license key is paused by administrator."
            response_data = {"success": False, "message": paused_msg}
        elif license_obj.status == "revoked":
            revoked_msg = getattr(app, "revoked_license_message", "") or "This license key has been revoked."
            response_data = {"success": False, "message": revoked_msg}
        elif license_obj.status == "used":
            user = db.query(User).filter(User.app_id == app.id, User.username == license_obj.used_by_username).first()
            if not user:
                user = db.query(User).filter(User.app_id == app.id, User.key_used == license_key).first()

            if not user:
                response_data = {"success": False, "message": "License was used but user profile is missing."}
            elif user.is_banned:
                ban_prefix = getattr(app, "banned_user_message", "") or "Account is banned!"
                response_data = {"success": False, "message": f"{ban_prefix} Reason: {user.ban_reason or 'No reason provided'}"}
            elif user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                exp_msg = getattr(app, "expired_sub_message", "") or "Your subscription has expired! Please renew."
                response_data = {"success": False, "message": exp_msg}
            else:
                is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
                if not user.hwid:
                    user.hwid = hwid
                    db.commit()

                if is_hwid_locked and user.hwid and user.hwid != hwid:
                    log_audit(db, app.id, "HWID_MISMATCH", username=user.username, ip_address=ip, hwid=hwid, details="License HWID mismatch", status="DANGER")
                    mismatch_msg = getattr(app, "hwid_mismatch_message", "") or "HWID Mismatch! This key is bound to another PC."
                    response_data = {"success": False, "message": mismatch_msg}
                else:
                    user.last_login = datetime.datetime.utcnow()
                    user.last_ip = ip
                    session.user_id = user.id
                    db.commit()

                    # Clear failed attempts on success
                    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
                    failed_attempts_tracker.pop(key, None)

                    log_audit(db, app.id, "LOGIN_SUCCESS", username=user.username, ip_address=ip, hwid=hwid, details="Logged in via key", status="SUCCESS")
                    lic_ok_msg = getattr(app, "license_login_success_message", "") or "License authenticated successfully!"
                    response_data = {
                        "success": True,
                        "message": lic_ok_msg,
                        "info": {
                            "username": user.username,
                            "subscription": user.subscription_tier,
                            "expiry": user.expires_at.isoformat() if user.expires_at else "Lifetime",
                            "hwid": user.hwid
                        }
                    }
        elif license_obj.status == "unused":
            # Auto create user with the key
            username = f"user_{generate_random_token(8)}"
            expires_at = None
            if license_obj.duration_days > 0 and license_obj.duration_days < 90000:
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=license_obj.duration_days)

            new_user = User(
                app_id=app.id,
                username=username,
                password_hash=None,
                hwid=hwid,
                last_ip=ip,
                registered_ip=ip,
                subscription_tier=license_obj.level,
                expires_at=expires_at,
                key_used=license_key,
                created_at=datetime.datetime.utcnow(),
                last_login=datetime.datetime.utcnow()
            )
            db.add(new_user)
            license_obj.status = "used"
            license_obj.used_by_username = username
            license_obj.used_at = datetime.datetime.utcnow()
            db.commit()

            session.user_id = new_user.id
            db.commit()

            # Clear failed attempts on success
            key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
            failed_attempts_tracker.pop(key, None)

            log_audit(db, app.id, "KEY_ACTIVATED", username=username, ip_address=ip, hwid=hwid, details="Key activated and locked to HWID", status="SUCCESS")
            response_data = {
                "success": True,
                "message": "License activated successfully!",
                "info": {
                    "username": username,
                    "subscription": new_user.subscription_tier,
                    "expiry": new_user.expires_at.isoformat() if new_user.expires_at else "Lifetime",
                    "hwid": new_user.hwid
                }
            }

    # ---------------- HEARTBEAT / SESSION WATCHDOG ----------------
    elif action == "heartbeat" or action == "ping" or action == "check":
        # 1. Check if application was put into Maintenance Mode or Disabled while client is running
        if app.status == "maintenance" or app.status == "paused":
            msg = getattr(app, "maintenance_message", "") or "🚨 Application is currently under maintenance! Session terminated."
            session.is_valid = False
            db.commit()
            response_data = {
                "success": False,
                "is_maintenance": True,
                "status": "maintenance",
                "message": msg
            }
        elif app.status == "disabled":
            msg = getattr(app, "custom_message", "") or "Application disabled by administrator."
            session.is_valid = False
            db.commit()
            response_data = {
                "success": False,
                "is_disabled": True,
                "status": "disabled",
                "message": msg
            }
        elif session.user_id:
            user = db.query(User).filter(User.id == session.user_id).first()
            if not user or user.is_banned:
                response_data = {"success": False, "message": "User session revoked or banned."}
            elif user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                response_data = {"success": False, "message": "Subscription expired during active session."}
            else:
                # Refresh session expiry
                session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=app.session_timeout_minutes)
                db.commit()

                # Fetch active notifications for live push
                from ..database import AppNotification
                notifs = db.query(AppNotification).filter(AppNotification.app_id == app.id, AppNotification.is_active == True).all()
                active_notifs = [
                    {"id": n.id, "title": n.title, "message": n.message, "type": n.type, "show_on_login": n.show_on_login}
                    for n in notifs
                ]

                response_data = {
                    "success": True,
                    "status": app.status,
                    "custom_status": getattr(app, "custom_status", "UNDETECTED") or "UNDETECTED",
                    "notifications": active_notifs,
                    "message": "Heartbeat acknowledged.",
                    "timestamp": int(datetime.datetime.utcnow().timestamp())
                }
        else:
            session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=app.session_timeout_minutes)
            db.commit()

            from ..database import AppNotification
            notifs = db.query(AppNotification).filter(AppNotification.app_id == app.id, AppNotification.is_active == True).all()
            active_notifs = [
                {"id": n.id, "title": n.title, "message": n.message, "type": n.type, "show_on_login": n.show_on_login}
                for n in notifs
            ]

            response_data = {
                "success": True,
                "status": app.status,
                "custom_status": getattr(app, "custom_status", "UNDETECTED") or "UNDETECTED",
                "notifications": active_notifs,
                "message": "Session active.",
                "timestamp": int(datetime.datetime.utcnow().timestamp())
            }

    # ---------------- CLOUD FILE / DOWNLOAD ----------------
    elif action == "file" or action == "download_file":
        file_id = (data.get("fileid") or data.get("file_id", "")).strip()
        file_obj = db.query(AppFile).filter(AppFile.app_id == app.id, AppFile.file_id == file_id).first()
        if not file_obj:
            response_data = {"success": False, "message": f"File with ID '{file_id}' not found."}
        else:
            response_data = {
                "success": True,
                "message": "File download authorized.",
                "file_name": file_obj.file_name,
                "file_url": file_obj.file_url,
                "file_size": file_obj.file_size
            }

    # ---------------- LOG TO DASHBOARD ----------------
    elif action == "log":
        msg = data.get("message", "")
        log_audit(db, app.id, "CLIENT_LOG", username=session.user.username if session.user else "", ip_address=ip, hwid=hwid, details=msg, status="INFO")
        response_data = {"success": True, "message": "Log recorded."}

    else:
        response_data = {"success": False, "message": f"Invalid action type: {action}"}

    # 3. Encrypt response with session AES key
    encrypted_response = aes_encrypt(json.dumps(response_data), session.encryption_key)
    signature = compute_hmac_signature(encrypted_response, session.encryption_key)

    return {
        "success": response_data.get("success", False),
        "data": encrypted_response,
        "signature": signature
    }



# ================= 3. DIRECT ENDPOINTS FOR SDK CLIENTS =================
class ClientLoginRequest(BaseModel):
    app_name: Optional[str] = ""
    app_token: Optional[str] = ""
    username: str
    password: str
    hwid: Optional[str] = ""
    sessionid: Optional[str] = ""

class ClientRegisterRequest(BaseModel):
    app_name: Optional[str] = ""
    app_token: Optional[str] = ""
    username: str
    password: str
    license_key: Optional[str] = ""
    key: Optional[str] = ""
    hwid: Optional[str] = ""
    sessionid: Optional[str] = ""

class ClientLicenseRequest(BaseModel):
    app_name: Optional[str] = ""
    app_token: Optional[str] = ""
    license_key: Optional[str] = ""
    key: Optional[str] = ""
    hwid: Optional[str] = ""
    sessionid: Optional[str] = ""

class ClientUpgradeRequest(BaseModel):
    app_name: Optional[str] = ""
    app_token: Optional[str] = ""
    username: str
    license_key: Optional[str] = ""
    key: Optional[str] = ""
    sessionid: Optional[str] = ""

class ClientVarRequest(BaseModel):
    app_name: Optional[str] = ""
    app_token: Optional[str] = ""
    var_name: Optional[str] = ""
    varid: Optional[str] = ""
    sessionid: Optional[str] = ""

def resolve_app_for_client(db: Session, app_name: str, app_token: str):
    app = None
    if app_token:
        app = db.query(Application).filter(Application.secret == app_token.strip()).first()
    if not app and app_name:
        if app_token:
            app = db.query(Application).filter(Application.name == app_name.strip(), Application.secret == app_token.strip()).first()
        else:
            app = db.query(Application).filter(Application.name == app_name.strip()).first()
    return app

@router.post("/login")
async def client_direct_login(data: ClientLoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    hwid = normalize_hwid(data.hwid)
    app = resolve_app_for_client(db, data.app_name, data.app_token)
    if not app:
        return {"success": False, "message": "Application not found or invalid app token."}

    username = data.username.strip()
    password = data.password

    user = db.query(User).filter(User.app_id == app.id, User.username == username).first()
    if not user:
        is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "User not found")
        if is_banned:
            return {"success": False, "message": getattr(app, "brute_force_ban_message", "") or "Too many failed attempts! Blacklisted."}
        log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Username not found", status="WARNING")
        return {"success": False, "message": getattr(app, "user_not_found_message", "") or "Username does not exist."}

    if user.is_banned:
        log_audit(db, app.id, "LOGIN_BLOCKED", username=username, ip_address=ip, hwid=hwid, details=f"Banned: {user.ban_reason}", status="DANGER")
        return {"success": False, "message": f"{getattr(app, 'banned_user_message', '') or 'Account is banned!'} Reason: {user.ban_reason or 'None'}"}

    if not verify_password(password, user.password_hash or ""):
        is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "Incorrect password")
        if is_banned:
            return {"success": False, "message": getattr(app, "brute_force_ban_message", "") or "Too many failed attempts! Blacklisted."}
        log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Incorrect password", status="WARNING")
        return {"success": False, "message": getattr(app, "login_failed_message", "") or "Invalid username or password."}

    if user.expires_at and datetime.datetime.utcnow() > user.expires_at:
        log_audit(db, app.id, "LOGIN_EXPIRED", username=username, ip_address=ip, hwid=hwid, details="Subscription expired", status="WARNING")
        return {"success": False, "message": getattr(app, "expired_sub_message", "") or "Your subscription has expired! Please renew."}

    is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
    if not user.hwid and hwid:
        user.hwid = hwid
        db.commit()

    if is_hwid_locked and user.hwid and hwid and user.hwid != hwid:
        log_audit(db, app.id, "HWID_MISMATCH", username=username, ip_address=ip, hwid=hwid, details="Hardware ID mismatch", status="DANGER")
        return {"success": False, "message": getattr(app, "hwid_mismatch_message", "") or "HWID Mismatch! Your account is locked to another computer."}

    user.last_login = datetime.datetime.utcnow()
    user.last_ip = ip
    db.commit()

    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
    failed_attempts_tracker.pop(key, None)

    log_audit(db, app.id, "LOGIN_SUCCESS", username=username, ip_address=ip, hwid=hwid, details="User successfully authenticated", status="SUCCESS")
    return {
        "success": True,
        "message": getattr(app, "login_success_message", "") or "Logged in successfully!",
        "username": user.username,
        "subscription": user.subscription_tier or "default",
        "expires_at": user.expires_at.isoformat() if user.expires_at else "Lifetime",
        "ip": ip,
        "hwid": user.hwid or ""
    }

@router.post("/register")
async def client_direct_register(data: ClientRegisterRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    hwid = normalize_hwid(data.hwid)
    app = resolve_app_for_client(db, data.app_name, data.app_token)
    if not app:
        return {"success": False, "message": "Application not found or invalid app token."}

    username = data.username.strip()
    password = data.password
    license_key = (data.license_key or data.key or "").strip()

    if not username or not password or not license_key:
        return {"success": False, "message": "Username, password, and license key are all required."}

    existing_user = db.query(User).filter(User.app_id == app.id, User.username == username).first()
    if existing_user:
        return {"success": False, "message": "Username is already registered."}

    license_obj = db.query(License).filter(License.app_id == app.id, License.license_key == license_key).first()
    if not license_obj:
        log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"Invalid key: {license_key}", status="WARNING")
        return {"success": False, "message": getattr(app, "invalid_license_message", "") or "Invalid license key."}

    if license_obj.status != "unused":
        log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"License already {license_obj.status}", status="WARNING")
        return {"success": False, "message": getattr(app, "used_license_message", "") or f"This license key is already {license_obj.status}."}

    expires_at = None
    if license_obj.duration_days > 0 and license_obj.duration_days < 90000:
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=license_obj.duration_days)

    new_user = User(
        app_id=app.id,
        username=username,
        password_hash=hash_password(password),
        hwid=hwid,
        last_ip=ip,
        registered_ip=ip,
        subscription_tier=license_obj.level,
        expires_at=expires_at,
        key_used=license_key,
        created_at=datetime.datetime.utcnow(),
        last_login=datetime.datetime.utcnow()
    )
    db.add(new_user)

    license_obj.status = "used"
    license_obj.used_by_username = username
    license_obj.used_at = datetime.datetime.utcnow()
    db.commit()

    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
    failed_attempts_tracker.pop(key, None)

    log_audit(db, app.id, "REGISTER_SUCCESS", username=username, ip_address=ip, hwid=hwid, details=f"Registered account with key {license_key}", status="SUCCESS")
    return {
        "success": True,
        "message": getattr(app, "register_success_message", "") or "Account created successfully! You are now logged in.",
        "username": new_user.username,
        "subscription": new_user.subscription_tier or "default",
        "expires_at": new_user.expires_at.isoformat() if new_user.expires_at else "Lifetime",
        "ip": ip,
        "hwid": new_user.hwid or ""
    }

@router.post("/license")
async def client_direct_license(data: ClientLicenseRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    hwid = normalize_hwid(data.hwid)
    app = resolve_app_for_client(db, data.app_name, data.app_token)
    if not app:
        return {"success": False, "message": "Application not found or invalid app token."}

    license_key = (data.license_key or data.key or "").strip()
    if not license_key:
        return {"success": False, "message": "License key is required."}

    license_obj = db.query(License).filter(License.app_id == app.id, License.license_key == license_key).first()
    if not license_obj:
        log_audit(db, app.id, "LICENSE_FAIL", ip_address=ip, hwid=hwid, details=f"Invalid key {license_key}", status="WARNING")
        return {"success": False, "message": getattr(app, "invalid_license_message", "") or "Invalid license key."}

    if license_obj.status == "paused":
        return {"success": False, "message": getattr(app, "paused_license_message", "") or "This license key is paused by administrator."}

    if license_obj.status == "revoked":
        return {"success": False, "message": getattr(app, "revoked_license_message", "") or "This license key has been revoked."}

    if license_obj.status == "used":
        user = db.query(User).filter(User.app_id == app.id, User.username == license_obj.used_by_username).first()
        if not user:
            user = db.query(User).filter(User.app_id == app.id, User.key_used == license_key).first()

        if not user:
            return {"success": False, "message": "License was used but user profile is missing."}
        if user.is_banned:
            return {"success": False, "message": f"{getattr(app, 'banned_user_message', '') or 'Account is banned!'} Reason: {user.ban_reason or 'None'}"}
        if user.expires_at and datetime.datetime.utcnow() > user.expires_at:
            return {"success": False, "message": getattr(app, "expired_sub_message", "") or "Your subscription has expired! Please renew."}

        is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
        if not user.hwid and hwid:
            user.hwid = hwid
            db.commit()

        if is_hwid_locked and user.hwid and hwid and user.hwid != hwid:
            log_audit(db, app.id, "HWID_MISMATCH", username=user.username, ip_address=ip, hwid=hwid, details="License HWID mismatch", status="DANGER")
            return {"success": False, "message": getattr(app, "hwid_mismatch_message", "") or "HWID Mismatch! This key is bound to another PC."}

        user.last_login = datetime.datetime.utcnow()
        user.last_ip = ip
        db.commit()

        log_audit(db, app.id, "LOGIN_SUCCESS", username=user.username, ip_address=ip, hwid=hwid, details="Logged in via key", status="SUCCESS")
        return {
            "success": True,
            "message": getattr(app, "license_login_success_message", "") or "License authenticated successfully!",
            "username": user.username,
            "subscription": user.subscription_tier or "default",
            "expires_at": user.expires_at.isoformat() if user.expires_at else "Lifetime",
            "ip": ip,
            "hwid": user.hwid or ""
        }

    elif license_obj.status == "unused":
        username = f"user_{generate_random_token(8)}"
        expires_at = None
        if license_obj.duration_days > 0 and license_obj.duration_days < 90000:
            expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=license_obj.duration_days)

        new_user = User(
            app_id=app.id,
            username=username,
            password_hash=None,
            hwid=hwid,
            last_ip=ip,
            registered_ip=ip,
            subscription_tier=license_obj.level,
            expires_at=expires_at,
            key_used=license_key,
            created_at=datetime.datetime.utcnow(),
            last_login=datetime.datetime.utcnow()
        )
        db.add(new_user)
        license_obj.status = "used"
        license_obj.used_by_username = username
        license_obj.used_at = datetime.datetime.utcnow()
        db.commit()

        log_audit(db, app.id, "KEY_ACTIVATED", username=username, ip_address=ip, hwid=hwid, details="Key activated and locked to HWID", status="SUCCESS")
        return {
            "success": True,
            "message": "License activated successfully!",
            "username": username,
            "subscription": new_user.subscription_tier or "default",
            "expires_at": new_user.expires_at.isoformat() if new_user.expires_at else "Lifetime",
            "ip": ip,
            "hwid": new_user.hwid or ""
        }

@router.post("/upgrade")
async def client_direct_upgrade(data: ClientUpgradeRequest, request: Request, db: Session = Depends(get_db)):
    ip = get_client_ip(request)
    app = resolve_app_for_client(db, data.app_name, data.app_token)
    if not app:
        return {"success": False, "message": "Application not found or invalid app token."}

    username = data.username.strip()
    license_key = (data.license_key or data.key or "").strip()

    user = db.query(User).filter(User.app_id == app.id, User.username == username).first()
    if not user:
        return {"success": False, "message": "User does not exist."}

    license_obj = db.query(License).filter(License.app_id == app.id, License.license_key == license_key).first()
    if not license_obj or license_obj.status != "unused":
        return {"success": False, "message": "Invalid or already used license key."}

    # Extend expiration
    if license_obj.duration_days > 0:
        base_time = user.expires_at if (user.expires_at and user.expires_at > datetime.datetime.utcnow()) else datetime.datetime.utcnow()
        user.expires_at = base_time + datetime.timedelta(days=license_obj.duration_days)
    else:
        user.expires_at = None # Lifetime

    user.subscription_tier = license_obj.level
    license_obj.status = "used"
    license_obj.used_by_username = username
    license_obj.used_at = datetime.datetime.utcnow()
    db.commit()

    log_audit(db, app.id, "USER_UPGRADE", username=username, ip_address=ip, details=f"Upgraded with key {license_key}", status="SUCCESS")
    return {
        "success": True,
        "message": f"Successfully extended subscription by {license_obj.duration_days} days!",
        "username": user.username,
        "subscription": user.subscription_tier,
        "expires_at": user.expires_at.isoformat() if user.expires_at else "Lifetime"
    }

@router.post("/var")
async def client_direct_var(data: ClientVarRequest, request: Request, db: Session = Depends(get_db)):
    app = resolve_app_for_client(db, data.app_name, data.app_token)
    if not app:
        return {"success": False, "message": "Application not found."}

    var_name = (data.var_name or data.varid or "").strip()
    var_obj = db.query(AppVariable).filter(AppVariable.app_id == app.id, AppVariable.name == var_name).first()
    if not var_obj:
        return {"success": False, "message": f"Variable '{var_name}' not found."}

    return {"success": True, "value": var_obj.value}


@router.post("/telemetry/visit")
async def record_website_visit(request: Request):
    """Receives frontend visitor telemetry and triggers real-time Discord webhook alert."""
    try:
        data = await request.json()
    except Exception:
        data = {}

    page = data.get("page") or "/"
    referrer = data.get("referrer") or ""
    screen = data.get("screen") or ""
    
    ip = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For") or request.client.host
    user_agent = request.headers.get("User-Agent") or ""
    country = request.headers.get("CF-IPCountry") or ""

    from server.config import notify_website_visitor
    notify_website_visitor(page_name=page, ip=ip, user_agent=user_agent, referrer=referrer, country=country, screen=screen)
    return {"status": "ok"}


@router.get("/changelog")
def get_public_changelog(db: Session = Depends(get_db)):
    """Returns chronological timeline of all published system updates and improvements."""
    from ..database import ChangelogEntry
    entries = db.query(ChangelogEntry).order_by(ChangelogEntry.created_at.desc()).all()
    return {
        "success": True,
        "count": len(entries),
        "updates": [
            {
                "id": e.id,
                "version": e.version,
                "title": e.title,
                "category": e.category,
                "description": e.description,
                "author": e.author,
                "created_at": e.created_at.strftime("%B %d, %Y") if e.created_at else "Recent"
            }
            for e in entries
        ]
    }
