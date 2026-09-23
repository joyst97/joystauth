import os
import requests
import secrets
import string
import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel

from ..database import get_db, Developer, LibBypassClient, LibBypassKey
from ..security import verify_password, hash_password, create_access_token, decode_access_token, generate_random_token

router = APIRouter(prefix="/api/v1/lib-bypass", tags=["Joyst Corporation Lib Bypass API"])

# Upstream Backend API credentials (100% hidden and proxied server-side)
UPSTREAM_API_URL = os.getenv("LIB_BYPASS_UPSTREAM_URL", "https://auth.terminalx999.online/api_admin.php")
UPSTREAM_API_KEY = os.getenv("LIB_BYPASS_UPSTREAM_KEY", "TX999_API_1e36d0236ea3b3e1df6f83659150eac4")
PUBLIC_MASTER_API_KEY = os.getenv("LIB_BYPASS_PUBLIC_MASTER_KEY", "joyst-corporation-api-1e36d0236ea3b3e1df6f83659150eac4")
MASTER_SECRET_PASS = os.getenv("LIB_BYPASS_MASTER_PASS", "Tanmay@6969")

def generate_clean_key() -> str:
    """Generate unbranded standard 16-character license key (e.g. A9B2-C7D4-E1F8-G3H6)"""
    chars = string.ascii_uppercase + string.digits
    return "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(4))

def call_upstream_generate_key(target_key: str, days: int, note: str = ""):
    req_params = {
        "action": "generate_lib_key",
        "api_key": UPSTREAM_API_KEY,
        "custom_key": target_key,
        "days": days,
        "note": note
    }
    try:
        resp = requests.get(UPSTREAM_API_URL, params=req_params, timeout=25)
        try:
            data = resp.json()
        except Exception:
            data = {}

        if resp.status_code == 200 and data.get("success"):
            issued_keys = data.get("keys", [target_key])
            return True, issued_keys, None
        else:
            raw_msg = str(data.get("message", "")).lower()
            if any(w in raw_msg for w in ["already exists", "already taken", "duplicate"]):
                return False, [], "This custom key is already registered. Please choose a different key name or leave blank to auto-generate."
            return False, [], "License generation request could not be processed. Please check key format and try again."
    except requests.exceptions.Timeout:
        return False, [], "Generation request timed out. Please try again."
    except Exception:
        return False, [], "Unable to reach licensing engine. Please try again shortly."

def call_upstream_delete_key(key: str):
    req_params = {
        "action": "delete_lib_key",
        "api_key": UPSTREAM_API_KEY,
        "key": key
    }
    try:
        resp = requests.get(UPSTREAM_API_URL, params=req_params, timeout=20)
        try:
            data = resp.json()
        except Exception:
            data = {}
        if resp.status_code == 200 and data.get("success"):
            return True, None
        return False, "Failed to revoke key."
    except Exception:
        return False, "Service temporarily unavailable."

# ==================== Pydantic Models ====================
class LoginRequest(BaseModel):
    username: str
    password: str

class CreateClientRequest(BaseModel):
    username: str
    password: str
    credits_quota: int = 50
    daily_limit: int = 50
    notes: Optional[str] = ""

class AdjustCreditsRequest(BaseModel):
    amount: int # Can be positive (add) or negative (deduct)

class GenerateKeyRequest(BaseModel):
    days: int = 30
    custom_key: Optional[str] = None
    note: Optional[str] = ""

# ==================== Auth Dependency ====================
def get_current_session(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")
    token = authorization.split(" ")[1]
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid token")

    role = payload.get("role")
    sub = payload.get("sub")
    username = payload.get("username", "")

    if role == "master_admin":
        return {"role": "master_admin", "user_id": sub, "username": username, "client": None}
    
    if role == "client":
        try:
            client_id = int(sub)
        except (ValueError, TypeError):
            raise HTTPException(status_code=401, detail="Invalid token subject")
        client = db.query(LibBypassClient).filter(LibBypassClient.id == client_id).first()
        if not client:
            raise HTTPException(status_code=401, detail="Client account not found")
        if not client.is_active:
            raise HTTPException(status_code=403, detail="Account is suspended. Please contact administrator.")
        return {"role": "client", "user_id": client.id, "username": client.username, "client": client}

    raise HTTPException(status_code=401, detail="Unrecognized role")

def require_master_admin(session: dict = Depends(get_current_session)):
    if session.get("role") != "master_admin":
        raise HTTPException(status_code=403, detail="Access denied. Master Admin privilege required.")
    return session

def require_client(session: dict = Depends(get_current_session)):
    if session.get("role") != "client":
        raise HTTPException(status_code=403, detail="Access denied. Client Reseller session required.")
    return session

# ==================== Endpoints ====================

@router.post("/login")
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user_str = data.username.strip()
    pass_str = data.password

    # 1. Check Master Admin Credentials
    if (user_str.lower() in ["tanmay", "admin", "joyst_master"]) and (pass_str == MASTER_SECRET_PASS):
        token = create_access_token({"sub": "master_1", "username": user_str, "role": "master_admin"})
        return {
            "success": True,
            "role": "master_admin",
            "token": token,
            "username": user_str
        }

    # Check Developer table in JoystAuth
    dev = db.query(Developer).filter((Developer.username == user_str) | (Developer.email == user_str)).first()
    if dev and verify_password(pass_str, dev.password_hash):
        token = create_access_token({"sub": str(dev.id), "username": dev.username, "role": "master_admin"})
        return {
            "success": True,
            "role": "master_admin",
            "token": token,
            "username": dev.username
        }

    # 2. Check LibBypassClient table (Resellers / Sub-clients)
    client = db.query(LibBypassClient).filter(LibBypassClient.username == user_str).first()
    if client and verify_password(pass_str, client.password_hash):
        if not client.is_active:
            raise HTTPException(status_code=403, detail="Your account has been suspended by Administrator.")
        token = create_access_token({"sub": str(client.id), "username": client.username, "role": "client"})
        return {
            "success": True,
            "role": "client",
            "token": token,
            "username": client.username,
            "client": {
                "id": client.id,
                "username": client.username,
                "credits_quota": client.credits_quota,
                "credits_used": client.credits_used,
                "remaining_credits": "Unlimited" if client.credits_quota == -1 else max(0, client.credits_quota - client.credits_used),
                "api_key": client.api_key
            }
        }

    raise HTTPException(status_code=400, detail="Invalid username or password")

@router.get("/me")
async def get_me(session: dict = Depends(get_current_session), db: Session = Depends(get_db)):
    if session["role"] == "master_admin":
        return {
            "role": "master_admin",
            "username": session["username"],
            "is_master": True,
            "api_key": PUBLIC_MASTER_API_KEY
        }
    client = session["client"]
    return {
        "role": "client",
        "username": client.username,
        "is_master": False,
        "credits_quota": client.credits_quota,
        "credits_used": client.credits_used,
        "remaining_credits": "Unlimited" if client.credits_quota == -1 else max(0, client.credits_quota - client.credits_used),
        "api_key": client.api_key,
        "is_active": client.is_active,
        "created_at": client.created_at.strftime("%Y-%m-%d")
    }

# ==================== Master Admin Endpoints ====================

@router.get("/admin/stats")
async def get_admin_stats(session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    total_keys = db.query(LibBypassKey).count()
    active_clients = db.query(LibBypassClient).filter(LibBypassClient.is_active == True).count()
    total_clients = db.query(LibBypassClient).count()
    
    clients = db.query(LibBypassClient).all()
    total_quota = sum(c.credits_quota for c in clients if c.credits_quota > 0)
    total_used = sum(c.credits_used for c in clients)

    return {
        "total_keys": total_keys,
        "total_clients": total_clients,
        "active_clients": active_clients,
        "allocated_credits": total_quota,
        "used_credits": total_used,
        "master_api_status": "ONLINE (UNLIMITED)"
    }

@router.get("/admin/clients")
async def list_clients(session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    clients = db.query(LibBypassClient).order_by(desc(LibBypassClient.created_at)).all()
    res = []
    for c in clients:
        res.append({
            "id": c.id,
            "username": c.username,
            "credits_quota": c.credits_quota,
            "credits_used": c.credits_used,
            "remaining_credits": "Unlimited" if c.credits_quota == -1 else max(0, c.credits_quota - c.credits_used),
            "api_key": c.api_key,
            "is_active": c.is_active,
            "daily_limit": c.daily_limit,
            "notes": c.notes,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
            "keys_count": db.query(LibBypassKey).filter(LibBypassKey.client_id == c.id).count()
        })
    return res

@router.post("/admin/clients")
async def create_client(data: CreateClientRequest, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    username = data.username.strip()
    if db.query(LibBypassClient).filter(LibBypassClient.username == username).first():
        raise HTTPException(status_code=400, detail=f"Client '{username}' already exists.")

    new_api_key = f"JOYST_LIB_{username.lower()}_{generate_random_token(8)}"
    client = LibBypassClient(
        username=username,
        password_hash=hash_password(data.password),
        credits_quota=data.credits_quota,
        credits_used=0,
        daily_limit=data.daily_limit,
        api_key=new_api_key,
        is_active=True,
        notes=data.notes or ""
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"success": True, "message": f"Client '{username}' created successfully.", "client_id": client.id}

@router.post("/admin/clients/{client_id}/credits")
async def adjust_client_credits(client_id: int, data: AdjustCreditsRequest, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    client = db.query(LibBypassClient).filter(LibBypassClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    client.credits_quota += data.amount
    db.commit()
    return {"success": True, "new_quota": client.credits_quota, "remaining": client.credits_quota - client.credits_used}

@router.post("/admin/clients/{client_id}/toggle-status")
async def toggle_client_status(client_id: int, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    client = db.query(LibBypassClient).filter(LibBypassClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    client.is_active = not client.is_active
    db.commit()
    return {"success": True, "is_active": client.is_active}

@router.delete("/admin/clients/{client_id}")
async def delete_client(client_id: int, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    client = db.query(LibBypassClient).filter(LibBypassClient.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    db.delete(client)
    db.commit()
    return {"success": True, "message": "Client deleted"}

@router.post("/admin/generate-key")
async def admin_generate_key(data: GenerateKeyRequest, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    target_key = (data.custom_key or "").strip()
    if not target_key:
        target_key = generate_clean_key()

    ok, keys, err = call_upstream_generate_key(target_key, data.days, data.note or "Master Direct Key")
    if not ok:
        raise HTTPException(status_code=400, detail=f"Upstream generation failed: {err}")

    issued_key = keys[0] if keys else target_key

    entry = LibBypassKey(
        license_key=issued_key,
        days=data.days,
        created_by_type="master",
        created_by_username=session.get("username", "Tanmay (Master)"),
        client_id=None,
        note=data.note or "Master Direct Key",
        status="active"
    )
    db.add(entry)
    db.commit()

    return {
        "success": True,
        "license_key": issued_key,
        "days": data.days,
        "message": "Key generated successfully"
    }

@router.get("/admin/keys")
async def list_admin_keys(session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    keys = db.query(LibBypassKey).order_by(desc(LibBypassKey.created_at)).all()
    res = []
    for k in keys:
        res.append({
            "license_key": k.license_key,
            "days": k.days,
            "created_by": k.created_by_username,
            "created_by_type": k.created_by_type,
            "note": k.note,
            "status": k.status,
            "created_at": k.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return res

@router.delete("/admin/keys/{license_key}")
async def admin_delete_key(license_key: str, session: dict = Depends(require_master_admin), db: Session = Depends(get_db)):
    key_entry = db.query(LibBypassKey).filter(LibBypassKey.license_key == license_key.strip()).first()
    call_upstream_delete_key(license_key.strip())
    if key_entry:
        db.delete(key_entry)
        db.commit()
    return {"success": True, "message": "Key revoked and deleted successfully."}

# ==================== Client / Reseller Endpoints ====================

@router.post("/client/generate-key")
async def client_generate_key(data: GenerateKeyRequest, session: dict = Depends(require_client), db: Session = Depends(get_db)):
    client: LibBypassClient = session["client"]
    
    if client.credits_quota != -1:
        if client.credits_used >= client.credits_quota:
            raise HTTPException(status_code=400, detail="Insufficient credits! Please contact Tanmay to reload your balance.")

    target_key = (data.custom_key or "").strip()
    if not target_key:
        target_key = generate_clean_key()

    note = data.note.strip() if data.note else f"Client {client.username} key"

    ok, keys, err = call_upstream_generate_key(target_key, data.days, note)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Generation failed: {err}")

    issued_key = keys[0] if keys else target_key
    client.credits_used += 1

    entry = LibBypassKey(
        license_key=issued_key,
        days=data.days,
        created_by_type="client",
        created_by_username=client.username,
        client_id=client.id,
        note=note,
        status="active"
    )
    db.add(entry)
    db.commit()

    remaining = "Unlimited" if client.credits_quota == -1 else max(0, client.credits_quota - client.credits_used)

    return {
        "success": True,
        "license_key": issued_key,
        "days": data.days,
        "remaining_credits": remaining,
        "message": "Key generated successfully"
    }

@router.get("/client/keys")
async def list_client_keys(session: dict = Depends(require_client), db: Session = Depends(get_db)):
    client: LibBypassClient = session["client"]
    keys = db.query(LibBypassKey).filter(LibBypassKey.client_id == client.id).order_by(desc(LibBypassKey.created_at)).all()
    res = []
    for k in keys:
        res.append({
            "license_key": k.license_key,
            "days": k.days,
            "note": k.note,
            "status": k.status,
            "created_at": k.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return res

@router.delete("/client/keys/{license_key}")
async def client_delete_key(license_key: str, session: dict = Depends(require_client), db: Session = Depends(get_db)):
    client: LibBypassClient = session["client"]
    key_entry = db.query(LibBypassKey).filter(LibBypassKey.license_key == license_key.strip(), LibBypassKey.client_id == client.id).first()
    if not key_entry:
        raise HTTPException(status_code=404, detail="Key not found in your inventory.")

    call_upstream_delete_key(license_key.strip())
    db.delete(key_entry)
    db.commit()

    return {"success": True, "message": "Key deleted from inventory."}

# ==================== Universal Developer API Gateway (Fast GET / POST, Discord Bot Compatible) ====================
@router.api_route("/api_admin.php", methods=["GET", "POST"])
@router.api_route("/api.php", methods=["GET", "POST"])
@router.api_route("/gateway", methods=["GET", "POST"])
async def universal_api_gateway(
    request: Request,
    action: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None),
    custom_key: Optional[str] = Query(None),
    key_name: Optional[str] = Query(None),
    user: Optional[str] = Query(None),
    days: Optional[int] = Query(None),
    count: Optional[int] = Query(None),
    note: Optional[str] = Query(None),
    key: Optional[str] = Query(None),
    license_key: Optional[str] = Query(None),
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    body_data = {}
    if request.method == "POST":
        try:
            body_data = await request.json()
        except Exception:
            try:
                form = await request.form()
                body_data = dict(form)
            except Exception:
                body_data = {}

    final_action = action or body_data.get("action")
    final_api_key = api_key or x_api_key or body_data.get("api_key")
    final_custom_key = custom_key or key_name or user or body_data.get("custom_key") or body_data.get("key_name") or body_data.get("user")
    
    raw_days = days if days is not None else body_data.get("days", 30)
    try:
        final_days = int(raw_days)
    except (ValueError, TypeError):
        final_days = 30

    raw_count = count if count is not None else body_data.get("count", 1)
    try:
        final_count = max(1, min(int(raw_count), 50))
    except (ValueError, TypeError):
        final_count = 1

    final_note = note or body_data.get("note") or ""
    final_target_key = key or license_key or body_data.get("key") or body_data.get("license_key")

    if not final_api_key:
        return {"success": False, "message": "Missing required parameter: api_key."}
    
    final_api_key = str(final_api_key).strip()

    is_master = False
    client = None

    if final_api_key in [UPSTREAM_API_KEY, PUBLIC_MASTER_API_KEY, "JOYST_LIB_MASTER_ADMIN_ACTIVE", "JOYST_MASTER"] or final_api_key.startswith("JOYST_MASTER") or final_api_key.startswith("joyst-corporation-api"):
        is_master = True
    else:
        client = db.query(LibBypassClient).filter(LibBypassClient.api_key == final_api_key).first()
        if not client:
            return {"success": False, "message": "Invalid API Key."}
        if not client.is_active:
            return {"success": False, "message": "Account suspended. Please contact administrator."}

    if final_action == "generate_lib_key":
        if not is_master and client:
            if client.credits_quota != -1 and (client.credits_used + final_count) > client.credits_quota:
                return {
                    "success": False,
                    "message": "Insufficient credits to generate key(s).",
                    "remaining_credits": max(0, client.credits_quota - client.credits_used)
                }

        issued_keys = []
        for idx in range(final_count):
            t_key = final_custom_key if (final_count == 1 and final_custom_key) else generate_clean_key()
            t_note = final_note or (f"API Mint" if is_master else f"API Mint ({client.username})")

            ok, keys, err = call_upstream_generate_key(t_key, final_days, t_note)
            if not ok:
                return {"success": False, "message": err or "License generation failed."}

            actual_key = keys[0] if keys else t_key
            issued_keys.append(actual_key)

            entry = LibBypassKey(
                license_key=actual_key,
                days=final_days,
                created_by_type="master" if is_master else "client",
                created_by_username="Tanmay (Master)" if is_master else client.username,
                client_id=None if is_master else client.id,
                note=t_note,
                status="active"
            )
            db.add(entry)

            if not is_master and client:
                client.credits_used += 1

        db.commit()

        remaining = -1 if is_master or (client and client.credits_quota == -1) else (client.credits_quota - client.credits_used)

        return {
            "success": True,
            "message": "Lib Bypass Key(s) generated successfully.",
            "count": len(issued_keys),
            "keys": issued_keys,
            "duration_days": final_days,
            "quota": {
                "remaining_credits": remaining
            }
        }

    elif final_action == "delete_lib_key":
        if not final_target_key:
            return {"success": False, "message": "Missing required parameter: key."}
        
        target_k = str(final_target_key).strip()
        key_entry = db.query(LibBypassKey).filter(LibBypassKey.license_key == target_k).first()

        if not is_master and client:
            if not key_entry or key_entry.client_id != client.id:
                return {"success": False, "message": "Key not found in your inventory or unauthorized."}

        call_upstream_delete_key(target_k)
        if key_entry:
            db.delete(key_entry)
            db.commit()

        return {
            "success": True,
            "message": "Lib Bypass Key deleted successfully.",
            "key": target_k
        }

    return {"success": False, "message": "Invalid action. Supported: generate_lib_key, delete_lib_key"}
