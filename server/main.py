import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .config import send_discord_glitch_alert, send_discord_system_lifecycle_alert
from .api.client_api import router as client_router
from .api.admin_api import router as admin_router
from .api.auth_api import router as auth_router
from .api.reseller_api import router as reseller_router

app = FastAPI(
    title="Joyst Corporation Auth & Licensing Platform",
    description="Enterprise Multi-Tenant Zero-Leak Authentication & Licensing SaaS Platform.",
    version="2.0.0",
    docs_url=None,
    redoc_url=None
)

# Enable CORS for web requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BLOCKED_SCRAPER_KEYWORDS = [
    "httrack", "wget", "sitesucker", "teleport", "webcopier",
    "offline explorer", "webrip", "grabber", "extractor", "nikto",
    "sqlmap", "dirbuster", "gobuster", "wprecon", "masscan", "zgrab"
]

# Anti-Scraper, Zero-Leak Enclave & Anti-Stale-Cache Middleware
@app.middleware("http")
async def enclave_security_and_cache_middleware(request: Request, call_next):
    user_agent = (request.headers.get("user-agent") or "").lower()
    path = request.url.path

    # 1. Anti-Ripper Tool Blocker (Block known automated downloaders from stealing HTML/Assets)
    if any(k in user_agent for k in BLOCKED_SCRAPER_KEYWORDS):
        return JSONResponse(
            status_code=403,
            content={
                "success": False,
                "detail": "🛡️ ACCESS DENIED: Automated Scraping / Extraction Tool Intercepted by Joyst Zero-Leak Enclave Shield."
            }
        )

    try:
        response = await call_next(request)

        # 2. Hardened Security Headers
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # 3. Ensure browsers and proxies always fetch the freshest 0-second updated HTML/API
        if "text/html" in response.headers.get("content-type", "") or "application/json" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    except Exception as exc:
        import traceback
        tb = traceback.format_exc()
        client_ip = request.client.host if request.client else "Unknown"
        send_discord_glitch_alert(
            route=request.url.path,
            method=request.method,
            status_code=500,
            error_name=exc.__class__.__name__,
            error_msg=str(exc),
            stack_trace=tb,
            client_ip=client_ip
        )
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": "Internal Server Glitch: Incident intercepted and telemetry dispatched to administrator.",
                "error_type": exc.__class__.__name__
            }
        )

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

try:
    os.makedirs(STATIC_DIR, exist_ok=True)
    os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
    os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
    os.makedirs(TEMPLATES_DIR, exist_ok=True)
except Exception:
    pass

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Mount API Routers
app.include_router(client_router)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(reseller_router)

@app.on_event("startup")
async def on_startup():
    try:
        init_db()
    except Exception as e:
        print(f"[JOYST] Database init notice: {e}")

    # Auto-start Discord Bot in background if token is configured
    from .config import DISCORD_BOT_TOKEN
    token = (os.getenv("DISCORD_BOT_TOKEN") or DISCORD_BOT_TOKEN or "").strip()
    if token:
        try:
            import asyncio
            from .discord_bot import bot
            if bot:
                async def launch_bot():
                    try:
                        print(f"[JOYST BOT] Connecting Discord Bot with token (Length: {len(token)})...")
                        await bot.start(token)
                    except Exception as b_err:
                        print(f"[JOYST BOT ERROR] Bot run failed: {b_err}")

                asyncio.create_task(launch_bot())
                print("[JOYST BOT] Discord Bot background engine spawned successfully!")
        except Exception as err:
            print(f"[JOYST BOT] Discord Bot startup notice: {err}")
    else:
        print("[JOYST BOT] No DISCORD_BOT_TOKEN configured in environment variables.")

    send_discord_system_lifecycle_alert("STARTUP", "Joyst Auth Server v2.0.0 is online and healthy.")
    print("=======================================================")
    print("[JOYST CORPORATION] Production Platform is ONLINE [OK]")
    print("[+] Public Gateway:  https://joystauth.cc")
    print("[+] Status Endpoint: https://joystauth.cc/health")
    print("=======================================================")

@app.on_event("shutdown")
async def on_shutdown():
    send_discord_system_lifecycle_alert("RESTART", "Joyst Auth Server container reboot/redeployment in progress.")
    print("=======================================================")

@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.png", include_in_schema=False)
async def serve_favicon():
    logo_path = os.path.join(STATIC_DIR, "img", "joyst_logo.png")
    if os.path.exists(logo_path):
        return FileResponse(logo_path, media_type="image/png")
    return HTMLResponse("", status_code=204)

@app.get("/reseller/login", response_class=HTMLResponse)
async def serve_reseller_login(request: Request):
    reseller_login_file = os.path.join(TEMPLATES_DIR, "reseller_login.html")
    if os.path.exists(reseller_login_file):
        with open(reseller_login_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Reseller Login</h1>")

@app.get("/reseller/dashboard", response_class=HTMLResponse)
async def serve_reseller_dashboard(request: Request):
    reseller_dash_file = os.path.join(TEMPLATES_DIR, "reseller_dashboard.html")
    if os.path.exists(reseller_dash_file):
        with open(reseller_dash_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Reseller Dashboard</h1>")

@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def serve_landing(request: Request):
    landing_file = os.path.join(TEMPLATES_DIR, "landing.html")
    if os.path.exists(landing_file):
        with open(landing_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Joyst Corporation</h1>")

@app.get("/login", response_class=HTMLResponse)
async def serve_login(request: Request):
    login_file = os.path.join(TEMPLATES_DIR, "login.html")
    if os.path.exists(login_file):
        with open(login_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Login</h1>")

@app.get("/register", response_class=HTMLResponse)
async def serve_register(request: Request):
    reg_file = os.path.join(TEMPLATES_DIR, "register.html")
    if os.path.exists(reg_file):
        with open(reg_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Register</h1>")

@app.get("/dashboard", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    dash_file = os.path.join(TEMPLATES_DIR, "dashboard.html")
    if os.path.exists(dash_file):
        with open(dash_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Dashboard</h1>")

@app.get("/features", response_class=HTMLResponse)
async def serve_features(request: Request):
    f_file = os.path.join(TEMPLATES_DIR, "features.html")
    if os.path.exists(f_file):
        with open(f_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Features</h1>")

@app.get("/pricing", response_class=HTMLResponse)
async def serve_pricing(request: Request):
    p_file = os.path.join(TEMPLATES_DIR, "pricing.html")
    if os.path.exists(p_file):
        with open(p_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Pricing</h1>")

@app.get("/docs", response_class=HTMLResponse)
async def serve_docs(request: Request):
    d_file = os.path.join(TEMPLATES_DIR, "docs.html")
    if os.path.exists(d_file):
        with open(d_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Documentation</h1>")


@app.get("/changelog", response_class=HTMLResponse)
async def serve_changelog(request: Request):
    cl_file = os.path.join(TEMPLATES_DIR, "changelog.html")
    if os.path.exists(cl_file):
        with open(cl_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Changelog</h1>")
@app.get("/status", response_class=HTMLResponse)
async def serve_status(request: Request):
    s_file = os.path.join(TEMPLATES_DIR, "status.html")
    if os.path.exists(s_file):
        with open(s_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>System Status</h1>")

@app.get("/discord", response_class=HTMLResponse)
async def serve_discord(request: Request):
    d_file = os.path.join(TEMPLATES_DIR, "discord.html")
    if os.path.exists(d_file):
        with open(d_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>Discord Bot</h1>")

@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/v1/client/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "online", "version": "2.0.0", "service": "Joyst Corporation SaaS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)


@app.get("/api/v1/client/bot-status")
async def get_bot_status():
    from .config import DISCORD_BOT_TOKEN
    token = (os.getenv("DISCORD_BOT_TOKEN") or DISCORD_BOT_TOKEN or "").strip()
    from .discord_bot import bot, discord
    return {
        "bot_installed": discord is not None,
        "token_configured": bool(token),
        "token_length": len(token) if token else 0,
        "bot_is_ready": bool(bot.is_ready()) if (bot and discord) else False,
        "bot_user": str(bot.user) if (bot and discord and bot.user) else None,
        "latency_ms": round(bot.latency * 1000, 2) if (bot and discord and bot.latency and bot.latency > 0) else None
    }
