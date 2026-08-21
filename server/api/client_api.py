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
    app_token: Optional[str] = "" # Unified 1-Token parameter
    name: Optional[str] = ""      # Classic parameter
    ownerid: Optional[str] = ""   # Classic parameter
    secret: Optional[str] = ""    # Classic parameter
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

    # 1. Check if unified app_token was provided
    if data.app_token and data.app_token.strip():
        token_clean = data.app_token.strip()
        app = db.query(Application).filter(Application.secret == token_clean).first()
        if not app:
            app = db.query(Application).filter(Application.owner_id == token_clean).first()
    
    # 2. Check if classic 4-parameters were provided
    if not app and data.name and data.name.strip():
        app = db.query(Application).filter(
            Application.name == data.name.strip(),
            Application.owner_id == (data.ownerid or "").strip()
        ).first()

        if app and data.secret and app.secret != data.secret.strip():
            log_audit(db, app.id, "INIT_FAIL", ip_address=ip, hwid=hwid, details="Invalid Secret provided", status="DANGER")
            return {"success": False, "message": "Invalid Application Secret Key."}

    if not app:
        return {"success": False, "message": "Application does not exist or invalid credentials provided."}

    # Check Blacklist at init
    if hwid:
        bl_hwid = db.query(Blacklist).filter(Blacklist.app_id == app.id, Blacklist.type == "hwid", Blacklist.data == hwid).first()
        if bl_hwid:
            log_audit(db, app.id, "INIT_BLOCKED", ip_address=ip, hwid=hwid, details=f"HWID Blacklisted: {bl_hwid.reason}", status="DANGER")
            return {"success": False, "message": f"Your hardware ID is permanently banned from this application! ({bl_hwid.reason})"}

    if ip and ip != "127.0.0.1":
        bl_ip = db.query(Blacklist).filter(Blacklist.app_id == app.id, Blacklist.type == "ip", Blacklist.data == ip).first()
        if bl_ip:
            return {"success": False, "message": f"Your IP address is permanently blacklisted! ({bl_ip.reason})"}

    if app.status == "disabled":
        return {"success": False, "message": "This application is currently disabled by administrator."}

    if app.status == "paused":
        return {"success": False, "message": "Application is paused for maintenance. Please try again later."}

    # Strict Version Enforcement Check
    if app.version and data.version and app.version.strip() != data.version.strip():
        log_audit(db, app.id, "VERSION_MISMATCH", ip_address=ip, hwid=hwid, details=f"Client v{data.version} blocked. Latest is v{app.version}", status="WARNING")
        return {
            "success": False,
            "message": f"Update required! Latest version is v{app.version}, your client is v{data.version}.",
            "new_version": app.version,
            "download_url": app.download_link or ""
        }

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
        "app_version": app.version
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
            is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "Non-existent username")
            if is_banned:
                response_data = {"success": False, "message": "Too many invalid attempts! Your PC hardware and IP are permanently banned."}
            else:
                log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Username not found", status="WARNING")
                response_data = {"success": False, "message": "Username does not exist."}

        elif user.is_banned:
            log_audit(db, app.id, "LOGIN_BLOCKED", username=username, ip_address=ip, hwid=hwid, details=f"Banned: {user.ban_reason}", status="DANGER")
            response_data = {"success": False, "message": f"Account is banned! Reason: {user.ban_reason or 'No reason provided'}"}

        elif not verify_password(password, user.password_hash or ""):
            is_banned = check_and_record_failure(db, app.id, app.name, ip, hwid, username, "Incorrect password")
            if is_banned:
                response_data = {"success": False, "message": "Too many invalid attempts! Your PC hardware and IP are permanently banned."}
            else:
                log_audit(db, app.id, "LOGIN_FAILED", username=username, ip_address=ip, hwid=hwid, details="Incorrect password", status="WARNING")
                response_data = {"success": False, "message": "Password is incorrect."}

        else:
            if user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                log_audit(db, app.id, "LOGIN_EXPIRED", username=username, ip_address=ip, hwid=hwid, details="Subscription expired", status="WARNING")
                response_data = {"success": False, "message": "Your subscription has expired! Please renew."}
            else:
                # HWID Check
                is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
                if not user.hwid:
                    user.hwid = hwid
                    db.commit()
                    log_audit(db, app.id, "HWID_BIND", username=username, ip_address=ip, hwid=hwid, details="Hardware bound on first login", status="SUCCESS")

                if is_hwid_locked and user.hwid and user.hwid != hwid:
                    log_audit(db, app.id, "HWID_MISMATCH", username=username, ip_address=ip, hwid=hwid, details="Hardware ID mismatch", status="DANGER")
                    response_data = {
                        "success": False,
                        "message": "HWID Mismatch! Your account is locked to another computer. Contact administrator or use Discord bot to reset HWID."
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

                    response_data = {
                        "success": True,
                        "message": f"Logged in successfully! Welcome {user.username}",
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
                        response_data = {"success": False, "message": "Too many invalid attempts! Your PC hardware and IP are permanently banned."}
                    else:
                        log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"Invalid key provided: {license_key}", status="WARNING")
                        response_data = {"success": False, "message": "Invalid license key."}
                elif license_obj.status != "unused":
                    log_audit(db, app.id, "REGISTER_FAIL", username=username, ip_address=ip, hwid=hwid, details=f"License already {license_obj.status}", status="WARNING")
                    response_data = {"success": False, "message": f"This license key is already {license_obj.status}."}
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

                    response_data = {
                        "success": True,
                        "message": "Account created successfully! You are now logged in.",
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
                response_data = {"success": False, "message": "Too many invalid attempts! Your PC hardware and IP are permanently banned."}
            else:
                log_audit(db, app.id, "LICENSE_FAIL", ip_address=ip, hwid=hwid, details=f"Invalid key {license_key}", status="WARNING")
                response_data = {"success": False, "message": "Invalid license key."}
        elif license_obj.status == "paused":
            response_data = {"success": False, "message": "This license key is paused by administrator."}
        elif license_obj.status == "revoked":
            response_data = {"success": False, "message": "This license key has been revoked."}
        elif license_obj.status == "used":
            user = db.query(User).filter(User.app_id == app.id, User.username == license_obj.used_by_username).first()
            if not user:
                user = db.query(User).filter(User.app_id == app.id, User.key_used == license_key).first()

            if not user:
                response_data = {"success": False, "message": "License was used but user profile is missing."}
            elif user.is_banned:
                response_data = {"success": False, "message": f"Account banned: {user.ban_reason}"}
            elif user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                response_data = {"success": False, "message": "License subscription has expired."}
            else:
                is_hwid_locked = app.hwid_lock_enabled if user.hwid_lock_override is None else user.hwid_lock_override
                if not user.hwid:
                    user.hwid = hwid
                    db.commit()

                if is_hwid_locked and user.hwid and user.hwid != hwid:
                    log_audit(db, app.id, "HWID_MISMATCH", username=user.username, ip_address=ip, hwid=hwid, details="License HWID mismatch", status="DANGER")
                    response_data = {"success": False, "message": "HWID Mismatch! This key is bound to another PC."}
                else:
                    user.last_login = datetime.datetime.utcnow()
                    user.last_ip = ip
                    session.user_id = user.id
                    db.commit()

                    # Clear failed attempts on success
                    key = f"{app.id}_{hwid}" if hwid else f"{app.id}_{ip}"
                    failed_attempts_tracker.pop(key, None)

                    log_audit(db, app.id, "LOGIN_SUCCESS", username=user.username, ip_address=ip, hwid=hwid, details="Logged in via key", status="SUCCESS")
                    response_data = {
                        "success": True,
                        "message": "License authenticated successfully!",
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
    elif action == "heartbeat" or action == "ping":
        if session.user_id:
            user = db.query(User).filter(User.id == session.user_id).first()
            if not user or user.is_banned:
                response_data = {"success": False, "message": "User session revoked or banned."}
            elif user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                response_data = {"success": False, "message": "Subscription expired during active session."}
            else:
                # Refresh session expiry
                session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=app.session_timeout_minutes)
                db.commit()
                response_data = {"success": True, "message": "Heartbeat acknowledged.", "timestamp": int(datetime.datetime.utcnow().timestamp())}
        else:
            session.expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=app.session_timeout_minutes)
            db.commit()
            response_data = {"success": True, "message": "Session active.", "timestamp": int(datetime.datetime.utcnow().timestamp())}

    # ---------------- SECURITY ALERT / TAMPER DETECTED ----------------
    elif action == "security_alert" or action == "tamper_detected":
        reason = data.get("reason", "Debugger or Memory Tampering detected on client machine.")
        threat_name = data.get("threat", "Reverse Engineering Tool Detected")
        
        # Log high priority security incident
        log_audit(
            db, 
            app.id, 
            "TAMPER_DETECTED", 
            username=session.user.username if session.user else "Anonymous",
            ip_address=ip, 
            hwid=hwid, 
            details=f"🚨 Anti-Cheat Triggered: {threat_name} ({reason})", 
            status="DANGER"
        )
        
        # Invalidate session immediately
        session.is_valid = False
        db.commit()
        response_data = {"success": False, "message": "Security integrity violation. Session terminated."}

    # ---------------- CLOUD VARIABLE ----------------
    elif action == "var" or action == "get_var":
        var_name = data.get("varid") or data.get("var_name", "").strip()
        var_obj = db.query(AppVariable).filter(AppVariable.app_id == app.id, AppVariable.name == var_name).first()
        if not var_obj:
            response_data = {"success": False, "message": f"Variable '{var_name}' not found."}
        else:
            response_data = {"success": True, "message": var_obj.value, "value": var_obj.value}

    # ---------------- CHECK SESSION ----------------
    elif action == "check":
        if session.user_id:
            user = db.query(User).filter(User.id == session.user_id).first()
            if user and user.is_banned:
                response_data = {"success": False, "message": "User has been banned."}
            elif user and user.expires_at and datetime.datetime.utcnow() > user.expires_at:
                response_data = {"success": False, "message": "Subscription expired."}
            else:
                response_data = {"success": True, "message": "Session is active and valid."}
        else:
            response_data = {"success": True, "message": "Session is active."}

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
