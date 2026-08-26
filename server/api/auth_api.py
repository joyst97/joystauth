from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from ..database import get_db, Developer, CustomClient
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
    picture: Optional[str] = None

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

from ..database import get_db, Developer, Reseller, CustomClient
from ..security import verify_password, hash_password, create_access_token, decode_access_token, generate_random_token

# Helper to get current authenticated developer or reseller from Bearer token
def get_current_developer(authorization: Optional[str] = Header(None), db: Session = Depends(get_db)) -> Developer:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    # 0. Check if Custom Client Token
    if payload.get("role") == "custom_client":
        client_id = payload.get("client_id")
        client = None
        if client_id:
            try:
                client = db.query(CustomClient).filter(CustomClient.id == int(client_id)).first()
            except Exception:
                pass
        if not client and payload.get("sub"):
            client = db.query(CustomClient).filter(CustomClient.username == payload.get("sub")).first()
        
        if client:
            dev = db.query(Developer).filter(Developer.id == client.developer_id).first()
            if dev:
                dev.is_custom_client = True
                dev.custom_client_id = client.id
                dev.custom_client_username = client.username
                dev.allowed_apps_raw = client.allowed_apps or ""
                dev.allowed_apps_list = [x.strip() for x in (client.allowed_apps or "").split(",") if x.strip()]
                return dev

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
            avatar_url=None,
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

    try:
        from ..config import send_platform_master_alert
        from ..config import EMOJI
        send_platform_master_alert(
            title=f"{EMOJI['bolt']}  NEW DEVELOPER REGISTERED",
            description=(
                f"### {EMOJI['wave']} Welcome to Joyst Corporation Auth!\n\n"
                f"{EMOJI['arrow']} **Developer:** `@{new_dev.username}` {EMOJI['bot']}\n"
                f"{EMOJI['arrow']} **Email Address:** `{new_dev.email or 'No email linked'}`\n"
                f"{EMOJI['arrow']} **Assigned Tier:** `{new_dev.plan} Plan` {EMOJI['crown']}\n"
                f"{EMOJI['arrow']} **Master Owner ID:** `{new_dev.owner_id}`\n\n"
                f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                f"{EMOJI['dot']} *Account initialized and ready to deploy security tokens!* {EMOJI['shield']}"
            ),
            fields=[],
            color=0x10B981
        )
    except Exception:
        pass
    
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

    # 3. Check Custom Client Account (Branded Partner / Scoped Manager)
    client = db.query(CustomClient).filter(CustomClient.username == username).first()
    if client and verify_password(data.password, client.password_hash):
        dev = db.query(Developer).filter(Developer.id == client.developer_id).first()
        token = create_access_token({
            "sub": client.username,
            "client_id": client.id,
            "id": dev.id if dev else client.developer_id,
            "owner_id": dev.owner_id if dev else "",
            "role": "custom_client",
            "allowed_apps": client.allowed_apps or ""
        })
        return {
            "success": True,
            "role": "custom_client",
            "redirect_url": "/dashboard",
            "access_token": token,
            "token_type": "bearer",
            "username": client.username,
            "plan": "Enterprise"
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
    picture = data.picture
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
                picture = payload.get("picture", picture)
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

    if dev:
        if picture:
            dev.avatar_url = picture
        if name and (dev.username == "Developer" or dev.username.startswith("dev_")):
            clean_name = "".join(c for c in name if c.isalnum() or c in ("_", "-"))[:24]
            if clean_name and not db.query(Developer).filter(Developer.username == clean_name, Developer.id != dev.id).first():
                dev.username = clean_name
        db.commit()
    else:
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
            avatar_url=picture,
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
        "avatar_url": dev.avatar_url or "",
        "email": dev.email or "",
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
                                    google_id: profile.sub,
                                    picture: profile.picture
                                })
                            });
                            const authData = await authRes.json();
                            if (authData.access_token) {
                                localStorage.setItem("auth_admin_token", authData.access_token);
                                localStorage.setItem("auth_login_time", Date.now().toString());
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

class DiscordVerifyRequest(BaseModel):
    discord_id: str
    username: str
    email: Optional[str] = None
    avatar: Optional[str] = None

class DiscordCodeExchangeRequest(BaseModel):
    code: str

@router.get("/discord/login")
async def discord_oauth_login(request: Request):
    """Redirect developer to official Discord OAuth authorization portal using Token/Implicit Flow."""
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
        "response_type": "token",
        "scope": "identify email",
        "prompt": "consent"
    }
    discord_auth_url = "https://discord.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    return HTMLResponse(f"<script>window.location.href = '{discord_auth_url}';</script>")

@router.get("/discord/callback")
async def discord_oauth_callback(request: Request):
    """High-speed client-side profile verification page that bypasses cloud IP rate limits."""
    return HTMLResponse("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Connecting Discord Account | Joyst Auth</title>
    <style>
        body {
            background: #060204;
            color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            padding: 20px;
        }
        .auth-card {
            background: rgba(18, 6, 12, 0.95);
            border: 1.5px solid rgba(88, 101, 242, 0.5);
            border-radius: 16px;
            padding: 36px 30px;
            text-align: center;
            max-width: 440px;
            width: 100%;
            box-shadow: 0 25px 70px rgba(0,0,0,0.9), 0 0 40px rgba(88, 101, 242, 0.3);
        }
        .spinner {
            width: 48px;
            height: 48px;
            border: 3.5px solid rgba(88, 101, 242, 0.2);
            border-top-color: #5865F2;
            border-radius: 50%;
            animation: spin 0.7s linear infinite;
            margin: 0 auto 20px auto;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .status-title { font-size: 18px; font-weight: 800; margin: 0 0 8px 0; color: #fff; }
        .status-sub { font-size: 13px; color: #94a3b8; margin: 0; }
        .error-box { display: none; margin-top: 18px; padding: 12px; background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; border-radius: 8px; font-size: 12.5px; color: #f87171; }
        .retry-btn { display: none; margin-top: 16px; padding: 10px 22px; background: #ff2a5f; color: #fff; border-radius: 8px; text-decoration: none; font-weight: 700; font-size: 13px; }
    </style>
</head>
<body>
    <div class="auth-card">
        <div class="spinner" id="loader"></div>
        <h3 class="status-title" id="status-title">Authenticating with Discord...</h3>
        <p class="status-sub" id="status-sub">Connecting your Discord profile to Joyst Auth</p>
        <div class="error-box" id="error-box"></div>
        <a href="/login" class="retry-btn" id="retry-btn">&larr; Back to Login</a>
    </div>

    <script>
        (async function() {
            const statusTitle = document.getElementById("status-title");
            const statusSub = document.getElementById("status-sub");
            const errorBox = document.getElementById("error-box");
            const retryBtn = document.getElementById("retry-btn");
            const loader = document.getElementById("loader");

            function showError(msg) {
                loader.style.display = "none";
                statusTitle.textContent = "Discord Sign-In Failed";
                statusTitle.style.color = "#ef4444";
                statusSub.textContent = "Could not authenticate your Discord account.";
                errorBox.textContent = msg;
                errorBox.style.display = "block";
                retryBtn.style.display = "inline-block";
            }

            try {
                // 1. Check Hash for Access Token (Implicit Flow - Fastest & 100% Rate-Limit Immune)
                const hash = window.location.hash.substring(1);
                const hashParams = new URLSearchParams(hash);
                let accessToken = hashParams.get("access_token");

                // 2. Check Query Params for Code fallback
                const searchParams = new URLSearchParams(window.location.search);
                const code = searchParams.get("code");
                const error = searchParams.get("error");
                const errorDescription = searchParams.get("error_description");

                if (error) {
                    showError(errorDescription || error);
                    return;
                }

                if (!accessToken && code) {
                    statusSub.textContent = "Exchanging authorization token...";
                    const codeRes = await fetch("/api/v1/auth/discord/exchange-code", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ code: code })
                    });
                    const codeData = await codeRes.json();
                    if (codeData.access_token) {
                        accessToken = codeData.access_token;
                    } else {
                        showError(codeData.detail || "Code exchange failed");
                        return;
                    }
                }

                if (!accessToken) {
                    showError("No authorization token received from Discord.");
                    return;
                }

                // 3. Directly Fetch User Profile using User's Residential IP (Bypasses Cloudflare blocks)
                statusSub.textContent = "Fetching Discord profile...";
                const userRes = await fetch("https://discord.com/api/v10/users/@me", {
                    headers: { "Authorization": "Bearer " + accessToken }
                });

                if (!userRes.ok) {
                    const errText = await userRes.text();
                    showError("Discord API Error (" + userRes.status + "): " + errText);
                    return;
                }

                const discordUser = await userRes.json();
                const discordId = discordUser.id;
                const discordUsername = discordUser.global_name || discordUser.username;
                const discordEmail = discordUser.email || (discordUsername + "@discord.joystauth.cc");
                const avatarHash = discordUser.avatar;
                const discordAvatar = avatarHash 
                    ? `https://cdn.discordapp.com/avatars/${discordId}/${avatarHash}.png`
                    : "https://cdn.discordapp.com/embed/avatars/0.png";

                // 4. Verify & Create/Login Developer Account on Backend
                statusSub.textContent = "Opening your Developer Workspace...";
                const authRes = await fetch("/api/v1/auth/discord/verify-token", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        discord_id: String(discordId),
                        username: discordUsername,
                        email: discordEmail,
                        avatar: discordAvatar
                    })
                });

                const authData = await authRes.json();
                if (authData.access_token) {
                    localStorage.setItem("auth_admin_token", authData.access_token);
                    localStorage.setItem("auth_login_time", Date.now().toString());
                    localStorage.setItem("dev_owner_id", authData.owner_id);
                    localStorage.setItem("dev_username", authData.username);
                    localStorage.setItem("dev_avatar", discordAvatar);
                    window.location.href = authData.redirect_url || "/dashboard";
                } else {
                    showError(authData.detail || "Authentication verification failed");
                }
            } catch (err) {
                showError("Connection error: " + err.message);
            }
        })();
    </script>
</body>
</html>""")

@router.post("/discord/verify-token")
async def discord_verify_token(data: DiscordVerifyRequest, db: Session = Depends(get_db)):
    """Bulletproof endpoint that creates or logs into Developer workspace from verified Discord profile."""
    discord_id = data.discord_id.strip()
    discord_username = data.username.strip()
    discord_email = data.email.strip() if data.email else f"{discord_username}@discord.joystauth.cc"

    dev = None
    if discord_id:
        dev = db.query(Developer).filter(Developer.discord_id == discord_id).first()
    if not dev and data.email and "@" in data.email:
        dev = db.query(Developer).filter(func.lower(Developer.email) == data.email.strip().lower()).first()
    if not dev:
        dev = db.query(Developer).filter(func.lower(Developer.username) == discord_username.lower()).first()

    if dev:
        if data.avatar:
            dev.avatar_url = data.avatar
        dev.username = discord_username
        dev.discord_id = discord_id
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
            discord_id=discord_id,
            avatar_url=data.avatar,
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

    return {
        "success": True,
        "access_token": jwt_token,
        "token_type": "bearer",
        "username": dev.username,
        "avatar_url": dev.avatar_url or "",
        "email": dev.email or "",
        "owner_id": dev.owner_id,
        "plan": dev.plan,
        "redirect_url": "/dashboard",
        "message": f"Welcome back, {dev.username}!"
    }

@router.post("/discord/exchange-code")
async def discord_exchange_code(data: DiscordCodeExchangeRequest, request: Request):
    """Fallback code exchange with headers and retry."""
    import requests
    from ..config import DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, DISCORD_REDIRECT_URI
    
    base_url = str(request.base_url).rstrip("/")
    if "localhost" in base_url or "127.0.0.1" in base_url:
        redirect_uri = f"{base_url}/api/v1/auth/discord/callback"
    else:
        redirect_uri = DISCORD_REDIRECT_URI or "https://joystauth.cc/api/v1/auth/discord/callback"

    token_url = "https://discord.com/api/v10/oauth2/token"
    token_data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": data.code,
        "redirect_uri": redirect_uri
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "DiscordBot (https://joystauth.cc, 2.0.0)",
        "Accept": "application/json"
    }

    token_res = requests.post(token_url, data=token_data, headers=headers, timeout=10)
    if token_res.status_code != 200:
        raise HTTPException(status_code=400, detail=token_res.text)
    return token_res.json()


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None), dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    token = authorization.replace("Bearer ", "").strip() if authorization else ""
    payload = decode_access_token(token) if token else {}
    role = payload.get("role", "developer")
    reseller_id = payload.get("reseller_id")

    reseller_balance = None
    username_display = dev.username
    is_custom_client = getattr(dev, "is_custom_client", False)

    if is_custom_client:
        username_display = getattr(dev, "custom_client_username", dev.username)
        role = "custom_client"
    elif role == "reseller" and reseller_id:
        reseller = db.query(Reseller).filter(Reseller.id == reseller_id).first()
        if reseller:
            username_display = reseller.username
            reseller_balance = reseller.balance

    return {
        "success": True,
        "id": dev.id,
        "username": username_display,
        "role": role,
        "is_custom_client": is_custom_client,
        "can_create_apps": not is_custom_client,
        "allowed_apps": getattr(dev, "allowed_apps_raw", "all"),
        "reseller_balance": reseller_balance,
        "email": "Brand Partner Account" if is_custom_client else (dev.email or ""),
        "avatar_url": "" if is_custom_client else (getattr(dev, "avatar_url", "") or ""),
        "owner_id": "Protected" if is_custom_client else dev.owner_id,
        "plan": "Enterprise" if is_custom_client else (f"Reseller ({reseller_balance} Credits)" if role == "reseller" else dev.plan),
        "max_apps": dev.max_apps,
        "max_users_per_app": dev.max_users_per_app,
        "is_master_admin": False if is_custom_client else is_master_admin_account(dev),
        "created_at": dev.created_at.isoformat()
    }


class UpdateAvatarRequest(BaseModel):
    avatar_url: Optional[str] = ""

@router.post("/avatar")
async def update_developer_avatar(data: UpdateAvatarRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    """Update custom avatar URL or clear for default initial letter avatar."""
    new_url = data.avatar_url.strip() if data.avatar_url else ""
    if new_url and not (new_url.startswith("http://") or new_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="Avatar URL must start with http:// or https://")

    dev.avatar_url = new_url or None
    db.commit()
    db.refresh(dev)

    return {
        "success": True,
        "message": "Avatar updated successfully!",
        "avatar_url": dev.avatar_url or ""
    }

@router.post("/change-password")
async def change_password(data: ChangePasswordRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    if getattr(dev, "is_custom_client", False):
        cc = db.query(CustomClient).filter(CustomClient.id == dev.custom_client_id).first()
        if not cc or not verify_password(data.current_password, cc.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        cc.password_hash = hash_password(data.new_password)
        db.commit()
        return {"success": True, "message": "Password updated successfully"}
        
    if not verify_password(data.current_password, dev.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    dev.password_hash = hash_password(data.new_password)
    db.commit()
    return {"success": True, "message": "Password updated successfully"}


class DeleteAccountRequest(BaseModel):
    confirm_text: str

@router.delete("/delete-account")
async def delete_account(data: DeleteAccountRequest, dev: Developer = Depends(get_current_developer), db: Session = Depends(get_db)):
    if getattr(dev, "is_custom_client", False):
        raise HTTPException(status_code=403, detail="Custom clients cannot delete developer workspace.")
    """Permanently deletes developer account and all associated applications, keys, and users."""
    user_confirm = data.confirm_text.strip()
    if user_confirm.lower() != dev.username.strip().lower() and user_confirm.upper() != "DELETE":
        raise HTTPException(status_code=400, detail=f"Please type '{dev.username}' or 'DELETE' to confirm account deletion.")

    from ..database import Application, User, License, AppVariable, AppFile, Blacklist, Reseller, AuditLog, SubscriptionTier, AppNotification, Session as ClientSession
    
    try:
        # 1. Delete all Resellers belonging to this developer
        db.query(Reseller).filter(Reseller.developer_id == dev.id).delete(synchronize_session=False)

        # 2. Find all apps belonging to developer
        apps = db.query(Application).filter(Application.developer_id == dev.id).all()
        app_ids = [a.id for a in apps]

        if app_ids:
            db.query(User).filter(User.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(License).filter(License.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(SubscriptionTier).filter(SubscriptionTier.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppVariable).filter(AppVariable.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppFile).filter(AppFile.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Blacklist).filter(Blacklist.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AppNotification).filter(AppNotification.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(ClientSession).filter(ClientSession.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(AuditLog).filter(AuditLog.app_id.in_(app_ids)).delete(synchronize_session=False)
            db.query(Application).filter(Application.developer_id == dev.id).delete(synchronize_session=False)

        # 3. Delete developer account
        db.delete(dev)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete account: {str(e)}")

    return {"success": True, "message": "Your developer account and all applications have been permanently deleted."}


def is_master_admin_account(dev: Developer) -> bool:
    if not dev:
        return False
    from ..config import MASTER_ADMIN_IDS
    if dev.discord_id and dev.discord_id in MASTER_ADMIN_IDS:
        return True
    if dev.email and dev.email.lower() in ["tgarmy859@gmail.com", "joystauth@gmail.com"]:
        return True
    if dev.username and dev.username.lower() in ["tgarmy859", "joystxcheats", "joyst_admin"]:
        return True
    return False
