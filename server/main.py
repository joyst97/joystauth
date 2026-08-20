import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
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
    print("=======================================================")
    print("[JOYST CORPORATION] Platform is LIVE on http://localhost:8000")
    print("[+] Public Landing Page: http://localhost:8000")
    print("[+] Developer Sign Up:   http://localhost:8000/register")
    print("[+] Developer Login:     http://localhost:8000/login")
    print("[+] Developer Dashboard: http://localhost:8000/dashboard")
    print("[+] Reseller Login:      http://localhost:8000/reseller/login")
    print("[+] Reseller Dashboard:  http://localhost:8000/reseller/dashboard")
    print("=======================================================")

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

@app.get("/", response_class=HTMLResponse)
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

@app.get("/health")
async def health_check():
    return {"status": "online", "version": "2.0.0", "service": "Joyst Corporation SaaS"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
