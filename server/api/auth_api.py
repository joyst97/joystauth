from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from ..database import get_db, Developer
from ..security import verify_password, hash_password, create_access_token, decode_access_token, generate_random_token

router = APIRouter(prefix="/api/v1/auth", tags=["Developer Auth"])

class DeveloperRegisterRequest(BaseModel):
    username: str
    email: Optional[str] = ""
    password: str
    plan_key: Optional[str] = None

class DeveloperLoginRequest(BaseModel):
    username: str
    password: str

class GoogleAuthRequest(BaseModel):
    credential: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    google_id: Optional[str] = None

@router.get("/google/config")
async def get_google_config():
    import os
    client_id = os.getenv("GOOGLE_CLIENT_ID", "1029635040070-o00five90cn8ur7fhu4u5jnp8cbcdrla.apps.googleusercontent.com")
    return {
        "client_id": client_id,
        "is_configured": True
    }

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

from ..database import get_db, Developer, Reseller
from ..security import verify_password, hash_password, create_access_token, decode_access_token, generate_random_token

# Helper to get current authenticated developer or reseller from Bearer token
def get_current_developer(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Developer:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    dev = None
    # 1. Try finding by numeric/string id
    dev_id = payload.get("id")
    if dev_id:
        try:
            dev = db.query(Developer).filter(Developer.id == int(dev_id)).first()
        except Exception:
            pass
    
    # 2. Try finding by owner_id
    if not dev and payload.get("owner_id"):
        dev = db.query(Developer).filter(Developer.owner_id == payload["owner_id"]).first()
        
    # 3. Try finding by sub / username
    if not dev and payload.get("sub"):
        dev = db.query(Developer).filter(Developer.username == payload["sub"]).first()

    # 4. Try finding by email
    if not dev and payload.get("email"):
        dev = db.query(Developer).filter(Developer.email == payload["email"]).first()

    # 5. Fallback auto-recovery: If user was authenticated via JWT but database instance reset (e.g. Vercel serverless cold start), auto-recreate developer
    if not dev and (payload.get("sub") or payload.get("owner_id")):
        username = payload.get("sub") or "Developer"
        owner_id = payload.get("owner_id") or ("joyst_" + generate_random_token(12))
        email = payload.get("email")
        
        dev = Developer(
            username=username,
            email=email,
            password_hash=hash_password(generate_random_token(32)),
            owner_id=owner_id,
            plan="Paid",
            max_apps=999999,
            max_users_per_app=999999
        )
        try:
            db.add(dev)
            db.commit()
            db.refresh(dev)
        except Exception:
            db.rollback()
            dev = db.query(Developer).filter(Developer.username == username).first()
        
    if not dev:
        raise HTTPException(status_code=401, detail="Account workspace not found")
    return dev

@router.post("/register")
async def developer_register(data: DeveloperRegisterRequest, db: Session = Depends(get_db)):
    username = data.username.strip()
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    email = data.email.strip() if data.email else ""
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="A valid, real Email Address is strictly required to register.")

    existing_email = db.query(Developer).filter(Developer.email == email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="This email address is already registered. Please sign in.")

    existing = db.query(Developer).filter(Developer.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username is already taken")

    # Plan Determination
    assigned_plan = "Free"
    max_apps = 3
    max_users = 1000

    if data.plan_key and data.plan_key.strip():
        key_code = data.plan_key.strip().upper()
        # Check PlanKey in DB
        from ..database import PlanKey
        p_key = db.query(PlanKey).filter(PlanKey.key_code == key_code, PlanKey.is_used == False).first()
        if p_key:
            assigned_plan = "Paid"
            p_key.is_used = True
            p_key.used_by_username = username
        elif key_code.startswith("JOYST-PAID-") or key_code.startswith("JOYST-PRO-") or key_code.startswith("JOYST-DEV-") or key_code.startswith("JOYST-ENT-") or key_code == "PAID-UPGRADE-2026" or key_code == "DEV-UPGRADE-2026" or key_code == "ENT-UPGRADE-2026":
            assigned_plan = "Paid"
        else:
            raise HTTPException(status_code=400, detail="Invalid or expired Plan Upgrade Key. Leave blank for Free Plan.")

        if assigned_plan == "Paid":
            max_apps = 999999
            max_users = 999999

    owner_id = "joyst_" + generate_random_token(12)
    # Ensure owner_id is globally unique
    while db.query(Developer).filter(Developer.owner_id == owner_id).first():
        owner_id = "joyst_" + generate_random_token(12)

    new_dev = Developer(
        username=username,
        email=data.email.strip() if data.email else None,
        password_hash=hash_password(data.password),
        owner_id=owner_id,
        plan=assigned_plan,
        max_apps=max_apps,
        max_users_per_app=max_users
    )
    db.add(new_dev)
    db.commit()
    db.refresh(new_dev)

    token = create_access_token({"sub": new_dev.username, "id": new_dev.id, "owner_id": new_dev.owner_id})
    return {
        "success": True,
        "message": f"Account created with {assigned_plan} Plan! Welcome to Joyst Corporation Auth.",
        "access_token": token,
        "token_type": "bearer",
        "username": new_dev.username,
        "owner_id": new_dev.owner_id,
        "plan": new_dev.plan
    }

@router.post("/login")
async def developer_login(data: DeveloperLoginRequest, db: Session = Depends(get_db)):
    username = data.username.strip()
    
    # 1. Check Developer Account
    dev = db.query(Developer).filter(Developer.username == username).first()
    if dev and verify_password(data.password, dev.password_hash):
        token = create_access_token({
            "sub": dev.username,
            "id": dev.id,
            "owner_id": dev.owner_id,
            "role": "developer"
        })
        return {
            "success": True,
            "role": "developer",
            "redirect_url": "/dashboard",
            "access_token": token,
            "token_type": "bearer",
            "username": dev.username,
            "owner_id": dev.owner_id,
            "plan": dev.plan
        }
    
    # 2. Check Reseller Account (Smart Auto-Detection)
    reseller = db.query(Reseller).filter(Reseller.username == username).first()
    if reseller and verify_password(data.password, reseller.password_hash):
        token = create_access_token({
            "sub": str(reseller.id),
            "username": reseller.username,
            "role": "reseller"
        })
        return {
            "success": True,
            "role": "reseller",
            "redirect_url": "/reseller/dashboard",
            "access_token": token,
            "token_type": "bearer",
            "username": reseller.username,
            "balance": reseller.balance
        }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid username or password"
    )

@router.post("/google")
async def google_auth(data: GoogleAuthRequest, db: Session = Depends(get_db)):
    email = data.email.strip() if data.email else None
    name = data.name.strip() if data.name else None
    google_id = data.google_id.strip() if data.google_id else None

    # If credential JWT token is passed, decode payload safely
    if data.credential:
        import base64
        import json
        try:
            parts = data.credential.split(".")
            if len(parts) >= 2:
                padded = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
                payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
                email = payload.get("email", email)
                name = payload.get("name", payload.get("given_name", name))
                google_id = payload.get("sub", google_id)
        except Exception:
            pass

    if not email:
        raise HTTPException(status_code=400, detail="Google authentication did not provide a valid email.")

    # 1. Find developer by email
    dev = db.query(Developer).filter(Developer.email == email).first()

    # 2. If not found by email, try by name
    if not dev and name:
        clean_user = "".join(c for c in name if c.isalnum() or c in ("_", "-"))[:30]
        dev = db.query(Developer).filter(Developer.username == clean_user).first()

    # 3. If new user, create developer account automatically
    if not dev:
        base_username = email.split("@")[0]
        clean_username = "".join(c for c in base_username if c.isalnum() or c in ("_", "-"))[:24]
        if len(clean_username) < 3:
            clean_username = "dev_" + generate_random_token(6)

        username = clean_username
        counter = 1
        while db.query(Developer).filter(Developer.username == username).first():
            username = f"{clean_username}_{counter}"
            counter += 1

        owner_id = "joyst_" + generate_random_token(12)
        while db.query(Developer).filter(Developer.owner_id == owner_id).first():
            owner_id = "joyst_" + generate_random_token(12)

        random_pass = generate_random_token(32)

        dev = Developer(
            username=username,
            email=email,
            password_hash=hash_password(random_pass),
            owner_id=owner_id,
            plan="Free",
            max_apps=3,
            max_users_per_app=1000
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)

    token = create_access_token({
        "sub": dev.username,
        "id": dev.id,
        "owner_id": dev.owner_id,
        "role": "developer"
    })
    return {
        "success": True,
        "role": "developer",
        "redirect_url": "/dashboard",
        "access_token": token,
        "token_type": "bearer",
        "username": dev.username,
        "owner_id": dev.owner_id,
        "plan": dev.plan,
        "message": f"Welcome back, {dev.username}!"
    }

@router.get("/google/callback")
async def google_callback_redirect():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Connecting Google Account...</title>
        <style>
            body { background: #060204; color: #fff; font-family: -apple-system, BlinkMacSystemFont, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .loader { width: 44px; height: 44px; border: 3px solid rgba(225, 29, 72, 0.2); border-top-color: #ff2a5f; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px auto; }
            @keyframes spin { to { transform: rotate(360deg); } }
        </style>
    </head>
    <body>
        <div style="text-align: center;">
            <div class="loader"></div>
            <h3 style="margin: 0; font-size: 16px; font-weight: 700;">Connecting with Google...</h3>
            <p style="font-size: 13px; color: #94a3b8; margin-top: 6px;">Authenticating your developer workspace</p>
        </div>
        <script>
            (async function() {
                const hash = window.location.hash.substring(1);
                const params = new URLSearchParams(hash);
                const accessToken = params.get("access_token");
                if (accessToken) {
                    try {
                        const userRes = await fetch("https://www.googleapis.com/oauth2/v3/userinfo", {
                            headers: { Authorization: "Bearer " + accessToken }
                        });
                        const profile = await userRes.json();
                        if (profile && profile.email) {
                            const authRes = await fetch("/api/v1/auth/google", {
                                method: "POST",
                                headers: { "Content-Type": "application/json" },
                                body: JSON.stringify({
                                    email: profile.email,
                                    name: profile.name || profile.given_name,
                                    google_id: profile.sub
                                })
                            });
                            const authData = await authRes.json();
                            if (authData.access_token) {
                                localStorage.setItem("auth_admin_token", authData.access_token);
                                localStorage.setItem("dev_owner_id", authData.owner_id);
                                localStorage.setItem("dev_username", authData.username);
                                window.location.href = authData.redirect_url || "/dashboard";
                                return;
                            }
                        }
                    } catch (e) {
                        console.error(e);
                    }
                }
                window.location.href = "/login?error=google_failed";
            })();
        </script>
    </body>
    </html>
    """)

@router.get("/discord/login")
async def discord_oauth_login(request: Request):
    """Redirect developer to official Discord OAuth authorization portal."""
    import urllib.parse
    from ..config import DISCORD_CLIENT_ID, DISCORD_REDIRECT_URI
    
    base_url = str(request.base_url).rstrip("/")
    if "localhost" in base_url or "127.0.0.1" in base_url:
        redirect_uri = f"{base_url}/api/v1/auth/discord/callback"
    else:
        redirect_uri = DISCORD_REDIRECT_URI or "https://joystauth.cc/api/v1/auth/discord/callback"
        
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify email",
        "prompt": "consent"
    }
    discord_auth_url = "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    return HTMLResponse(f"<script>window.location.href = '{discord_auth_url}';</script>")

@router.get("/discord/callback")
async def discord_oauth_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None, db: Session = Depends(get_db)):
    """Exchange Discord OAuth code, create/login account, auto-join official server."""
    if error or not code:
        err_msg = error or "Authorization cancelled"
        return HTMLResponse(f"<script>window.location.href='/login?error={err_msg}';</script>")

    import requests
    from ..config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI, DISCORD_GUILD_ID, DISCORD_BOT_TOKEN
    
    base_url = str(request.base_url).rstrip("/")
    if "localhost" in base_url or "127.0.0.1" in base_url:
        redirect_uri = f"{base_url}/api/v1/auth/discord/callback"
    else:
        redirect_uri = DISCORD_REDIRECT_URI or "https://joystauth.cc/api/v1/auth/discord/callback"
    
    # 1. Exchange code for access token
    token_url = "https://discord.com/api/v10/oauth2/token"
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_res = requests.post(token_url, data=token_data, headers=headers)
    if token_res.status_code != 200:
        err_detail = token_res.text
        print(f"[DISCORD OAUTH ERROR] Token exchange failed ({token_res.status_code}): {err_detail}")
        return HTMLResponse(f"""
        <!DOCTYPE html>
        <html>
        <head><title>Discord Login Error</title></head>
        <body style="background:#09090b;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;padding:20px;text-align:center;">
            <div style="max-width:500px;background:#18181b;border:1px solid #ef4444;border-radius:12px;padding:26px;">
                <h3 style="color:#ef4444;margin-top:0;">Discord Sign-In Error</h3>
                <p style="font-size:13.5px;color:#cbd5e1;line-height:1.5;">Discord rejected the authorization. Ensure <strong>DISCORD_CLIENT_SECRET</strong> is set in your server environment and the Redirect URI below is added in your Discord Developer Portal:</p>
                <div style="background:#09090b;padding:10px;border-radius:6px;font-family:monospace;font-size:12px;color:#38bdf8;word-break:break-all;margin:12px 0;">{redirect_uri}</div>
                <div style="background:#09090b;padding:10px;border-radius:6px;font-family:monospace;font-size:12px;color:#f87171;word-break:break-word;margin:12px 0;">{err_detail}</div>
                <a href="/login" style="display:inline-block;background:#ff2a5f;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:700;font-size:13px;margin-top:8px;">&larr; Back to Login</a>
            </div>
        </body>
        </html>
        """)

    token_json = token_res.json()
    discord_access_token = token_json.get("access_token")

    # 2. Get Discord User Profile
    user_url = "https://discord.com/api/v10/users/@me"
    user_headers = {"Authorization": "Bearer " + str(discord_access_token)}
    user_res = requests.get(user_url, headers=user_headers)
    if user_res.status_code != 200:
        return HTMLResponse("<script>window.location.href='/login?error=discord_user_failed';</script>")

    discord_user = user_res.json()
    discord_id = discord_user.get("id")
    discord_username = discord_user.get("global_name") or discord_user.get("username")
    discord_email = discord_user.get("email") or f"{discord_username}@discord.joystauth.cc"
    
    avatar_hash = discord_user.get("avatar")
    if avatar_hash:
        discord_avatar = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png"
    else:
        discord_avatar = "https://cdn.discordapp.com/embed/avatars/0.png"

    # 3. Auto-join user to official Discord Server if configured
    if DISCORD_GUILD_ID and DISCORD_BOT_TOKEN:
        try:
            join_url = f"https://discord.com/api/v10/guilds/{DISCORD_GUILD_ID}/members/{discord_id}"
            join_headers = {
                "Authorization": "Bot " + str(DISCORD_BOT_TOKEN),
                "Content-Type": "application/json"
            }
            join_body = {"access_token": discord_access_token}
            requests.put(join_url, json=join_body, headers=join_headers, timeout=3)
        except Exception:
            pass

    # 4. Find or Create Developer Account
    dev = None
    if discord_id:
        dev = db.query(Developer).filter(Developer.discord_id == str(discord_id)).first()
    if not dev:
        dev = db.query(Developer).filter(Developer.email == discord_email).first()
    if not dev:
        dev = db.query(Developer).filter(Developer.username == discord_username).first()

    if dev:
        # Update with real Discord username and details
        dev.username = discord_username
        dev.discord_id = str(discord_id)
        if dev.plan == "Free":
            dev.plan = "Paid"
            dev.max_apps = 999999
            dev.max_users_per_app = 999999
        db.commit()
    else:
        clean_username = "".join(c for c in discord_username if c.isalnum() or c in ("_", "-"))[:24]
        if len(clean_username) < 3:
            clean_username = "dev_" + generate_random_token(6)

        username = clean_username
        counter = 1
        while db.query(Developer).filter(Developer.username == username).first():
            username = f"{clean_username}_{counter}"
            counter += 1

        owner_id = "joyst_" + generate_random_token(12)
        while db.query(Developer).filter(Developer.owner_id == owner_id).first():
            owner_id = "joyst_" + generate_random_token(12)

        random_pass = generate_random_token(32)
        dev = Developer(
            username=discord_username,
            email=discord_email,
            discord_id=str(discord_id),
            password_hash=hash_password(random_pass),
            owner_id=owner_id,
            plan="Paid",
            max_apps=999999,
            max_users_per_app=999999
        )
        db.add(dev)
        db.commit()
        db.refresh(dev)

    jwt_token = create_access_token({
        "sub": dev.username,
        "id": dev.id,
        "owner_id": dev.owner_id,
        "role": "developer"
    })

    redirect_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Connecting Discord Account...</title>
</head>
<body style="background:#060204;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="text-align:center;">
        <h3 style="margin:0;font-size:16px;">Welcome, {dev.username}!</h3>
        <p style="font-size:13px;color:#94a3b8;margin-top:6px;">Opening your Developer Workspace...</p>
    </div>
    <script>
        localStorage.setItem("auth_admin_token", "{jwt_token}");
        localStorage.setItem("dev_owner_id", "{dev.owner_id}");
        localStorage.setItem("dev_username", "{dev.username}");
        localStorage.setItem("dev_avatar", "{discord_avatar}");
        window.location.href = "/dashboard";
    </script>
</body>
</html>"""
    return HTMLResponse(redirect_html)

@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None), dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    payload = decode_access_token(token) if token else {}
    role = payload.get("role", "developer")
    reseller_id = payload.get("reseller_id")

    reseller_balance = None
    username_display = dev.username

    if role == "reseller" and reseller_id:
        reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
        if reseller:
            username_display = reseller.username
            reseller_balance = reseller.balance

    return {
        "success": True,
        "id": dev.id,
        "username": username_display,
        "role": role,
        "reseller_balance": reseller_balance,
        "email": dev.email or "",
        "owner_id": dev.owner_id,
        "plan": f"Reseller ({reseller_balance} Credits)" if role == "reseller" else dev.plan,
        "max_apps": dev.max_apps,
        "max_users_per_app": dev.max_users_per_app,
        "created_at": dev.created_at.isoformat()
    }

@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if not verify_password(data.current_password, dev.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    
    dev.password_hash = hash_password(data.new_password)
    db.commit()
    return {"success": True, "message": "Password updated successfully"}
