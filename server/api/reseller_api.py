import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from jose import JWTError, jwt

from ..database import get_db, Developer, Application, License, User, Reseller
from ..security import verify_password, create_access_token, decode_access_token, generate_license_key
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

class ResellerHwidResetRequest(BaseModel):
    app_id: int
    username: str

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
            allowed_apps_list.append({"id": app.id, "name": app.name, "version": app.version})

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

@router.get("/licenses")
async def list_reseller_licenses(reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    keys = db.query(License).filter(License.created_by_reseller == reseller.username).order_by(License.created_at.desc()).all()
    return {
        "success": True,
        "licenses": [
            {
                "id": k.id,
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
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == reseller.developer_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Check application permissions (supports multiple apps comma separated)
    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    if "all" not in allowed_apps_raw and str(app.id) not in allowed_apps_raw and app.name not in allowed_apps_raw:
        raise HTTPException(status_code=403, detail="You do not have permission to generate keys for this application")
    
    if data.count < 1 or data.count > 500:
        raise HTTPException(status_code=400, detail="Key count must be between 1 and 500")

    if reseller.balance < data.count:
        raise HTTPException(status_code=400, detail=f"Insufficient key credits! You have {reseller.balance} credits, but requested {data.count}.")

    generated_keys = []
    for _ in range(data.count):
        raw_key = generate_license_key(data.mask or "JOYST-XXXX-XXXX-XXXX")
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

    # Deduct reseller credits
    reseller.balance -= data.count
    db.commit()

    log_audit(
        db,
        app.id,
        "KEYS_GENERATED",
        username=reseller.username,
        details=f"Reseller '{reseller.username}' generated {data.count} keys (Balance: {reseller.balance})",
        status="SUCCESS"
    )

    return {
        "success": True,
        "message": f"Successfully generated {data.count} keys! Remaining balance: {reseller.balance} credits.",
        "keys": generated_keys,
        "remaining_balance": reseller.balance
    }

@router.post("/reset-hwid")
async def reseller_reset_hwid(data: ResellerHwidResetRequest, reseller: Reseller = Depends(get_current_reseller), db: Session = Depends(get_db)):
    app = db.query(Application).filter(Application.id == data.app_id, Application.developer_id == reseller.developer_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    allowed_apps_raw = [x.strip() for x in (reseller.allowed_apps or "all").split(",")]
    if "all" not in allowed_apps_raw and str(app.id) not in allowed_apps_raw and app.name not in allowed_apps_raw:
        raise HTTPException(status_code=403, detail="Permission denied for this application")

    user = db.query(User).filter(User.app_id == app.id, User.username == data.username.strip()).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found in this application")

    old_hwid = user.hwid
    user.hwid = None
    db.commit()

    log_audit(
        db,
        app.id,
        "HWID_RESET",
        username=user.username,
        details=f"HWID reset performed by Reseller '{reseller.username}' (Previous: {old_hwid[:12] if old_hwid else 'None'}...)",
        status="SUCCESS"
    )

    return {"success": True, "message": f"HWID lock successfully reset for user '{user.username}'!"}
