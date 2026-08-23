import os
import requests
import datetime
from sqlalchemy.orm import Session
from .database import Developer, AuditLog, Application, SessionLocal
from .security import hash_password, generate_random_token

PLATFORM_NAME = "JOYST CORPORATION"
PLATFORM_VERSION = "2.0.0"
DEFAULT_DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1538975515598262293/MkIFWJpXI3jU91daFhP5K6vHTL0Mzvkyh0wkupDmDbNu8auABjaQJ5hkgfpg6nYD_UCa"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "1029635040070-o00five90cn8ur7fhu4u5jnp8cbcdrla.apps.googleusercontent.com")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "1540058805138882730")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://joystauth.cc/api/v1/auth/discord/callback")

ACTION_TITLES = {
    "LOGIN_SUCCESS": "🟢 User Login Successful",
    "LOGIN_FAILED": "⚠️ Failed Login Attempt",
    "LOGIN_BLOCKED": "🚫 Login Blocked (Account Banned)",
    "LOGIN_EXPIRED": "⏳ Subscription Expired",
    "HWID_MISMATCH": "🚨 Hardware ID (HWID) Mismatch Blocked",
    "HWID_RESET": "🔄 Hardware ID (HWID) Reset",
    "HWID_BIND": "🔒 Hardware ID Bound to Machine",
    "REGISTER": "📝 New User Registered",
    "REGISTER_SUCCESS": "📝 New User Registered",
    "REGISTER_FAIL": "⚠️ Registration Failed",
    "LICENSE_FAIL": "❌ Invalid License Key Used",
    "KEYS_GENERATED": "🔑 License Keys Generated",
    "APP_CREATED": "⚡ New Application Created",
    "MANUAL_USER_CREATE": "👤 User Created Manually",
    "BAN_USER": "🔨 User Account Banned",
    "UNBAN_USER": "🔓 User Account Unbanned",
    "PAUSE_KEY": "⏸️ License Key Paused",
    "RESUME_KEY": "▶️ License Key Resumed",
    "REVOKE_KEY": "🗑️ License Key Revoked",
    "ADD_RESELLER": "💼 New Reseller Added",
    "ADD_BLACKLIST": "🚫 Blacklist Entry Added",
    "SECURITY_BAN": "🚨 BRUTE FORCE DETECTED - PERMANENT HWID/IP AUTO-BAN"
}

def log_audit(db: Session, app_id: int = None, action: str = "ACTION", username: str = "", ip_address: str = "", hwid: str = "", details: str = "", status: str = "INFO", extra_data: dict = None):
    """Record an audit log and dispatch rich Discord webhook without overriding webhook profile."""
    try:
        log_entry = AuditLog(
            app_id=app_id,
            username=username,
            action=action,
            ip_address=ip_address,
            hwid=hwid,
            details=details,
            status=status,
            timestamp=datetime.datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()

        target_webhook = DEFAULT_DISCORD_WEBHOOK_URL
        app_name = "JOYST AUTH"
        bot_name = "JOYST AUTH SHIELD"
        avatar_url = "https://joystauth.cc/static/img/joyst_logo.png"

        if app_id:
            app = db.query(Application).filter(Application.id == app_id).first()
            if app:
                app_name = app.name
                if app.webhook_bot_name:
                    bot_name = app.webhook_bot_name
                if app.webhook_avatar_url:
                    avatar_url = app.webhook_avatar_url
                if app.webhook_url and app.webhook_url.startswith("http"):
                    target_webhook = app.webhook_url

                # Granular Event Filtering Check
                if action == "LOGIN_SUCCESS" and not getattr(app, "webhook_on_login", True):
                    return
                if (action == "LOGIN_FAILED" or action == "LOGIN_BLOCKED") and not getattr(app, "webhook_on_failed", True):
                    return
                if (action == "HWID_MISMATCH" or action == "HWID_RESET") and not getattr(app, "webhook_on_hwid_reset", True):
                    return
                if (action == "REGISTER" or action == "REGISTER_SUCCESS" or action == "LICENSE_REDEEM") and not getattr(app, "webhook_on_register", True):
                    return
                if (action == "KEYS_GENERATED") and not getattr(app, "webhook_on_key_gen", True):
                    return
                if ("BAN" in action or action == "SECURITY_BAN") and not getattr(app, "webhook_on_ban", True):
                    return

        if target_webhook:
            import threading
            threading.Thread(
                target=send_discord_webhook,
                args=(target_webhook, app_name, action, username, ip_address, hwid, status, details, extra_data, bot_name, avatar_url),
                daemon=True
            ).start()
    except Exception as e:
        print(f"[AUDIT LOG ERROR] {e}")

def send_discord_webhook(webhook_url: str, app_name: str, action: str, username: str, ip: str, hwid: str, status: str, details: str, extra_data: dict = None, bot_name: str = "JOYST AUTH SHIELD", avatar_url: str = "https://joystauth.cc/static/img/joyst_logo.png"):
    """Send clean, rich Discord webhook embed with KeyAuth-grade aesthetic styling in background thread."""
    if not webhook_url or not webhook_url.startswith("http"):
        return

    color = 0x10B981 # Emerald Green for Success
    if action == "SECURITY_BAN" or status == "DANGER" or "MISMATCH" in action or "BAN" in action or "BLOCKED" in action:
        color = 0xDC2626 # Crimson Red for Security / Ban
    elif status == "WARNING" or "FAIL" in action or "EXPIRED" in action:
        color = 0xF59E0B # Amber Orange for Warnings / Failed logins
    elif "KEY" in action or "APP" in action or "RESELLER" in action:
        color = 0x8B5CF6 # Electric Purple for Administrative actions

    title = ACTION_TITLES.get(action, f"🔔 Event: {action}")

    fields = [
        {"name": "📱 Application", "value": f"**{app_name}**", "inline": True},
        {"name": "👤 Client User", "value": f"`{username or 'N/A'}`", "inline": True},
        {"name": "🌐 IP Address", "value": f"`{ip or 'Unknown'}`", "inline": True}
    ]

    if hwid:
        fields.append({"name": "💻 Motherboard HWID", "value": f"`{hwid}`", "inline": False})

    if extra_data:
        for k, v in extra_data.items():
            fields.append({"name": k, "value": str(v), "inline": True})

    if details:
        fields.append({"name": "📋 Audit Details", "value": details, "inline": False})

    payload = {
        "username": bot_name or "JOYST AUTH SHIELD",
        "avatar_url": avatar_url or "https://joystauth.cc/static/img/joyst_logo.png",
        "embeds": [
            {
                "title": title,
                "color": color,
                "fields": fields,
                "footer": {"text": f"JOYST CORPORATION AUTH • {app_name} Security Enclave"},
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }

    try:
        requests.post(webhook_url, json=payload, timeout=3)
    except Exception:
        pass

def send_discord_glitch_alert(route: str, method: str, status_code: int, error_name: str, error_msg: str, stack_trace: str = "", client_ip: str = "Unknown"):
    """Dispatches a modern, clean Cyber Crimson Embed to Discord whenever a server glitch or unhandled exception occurs."""
    target_webhook = os.getenv("INCIDENT_DISCORD_WEBHOOK_URL", DEFAULT_DISCORD_WEBHOOK_URL)
    if not target_webhook or not target_webhook.startswith("http"):
        return

    import threading
    def _post():
        fields = [
            {"name": "🌐 Endpoint Route", "value": f"`{method} {route}`", "inline": True},
            {"name": "📊 Status Code", "value": f"`{status_code}`", "inline": True},
            {"name": "💻 Origin Client IP", "value": f"`{client_ip or 'Unknown'}`", "inline": True},
            {"name": "⚠️ Exception Type", "value": f"**`{error_name}`**", "inline": False},
            {"name": "📄 Glitch Summary", "value": f"`{error_msg[:300]}`", "inline": False}
        ]

        if stack_trace:
            trace_snippet = stack_trace[-750:] if len(stack_trace) > 750 else stack_trace
            fields.append({
                "name": "🔍 Stack Trace Forensics",
                "value": f"```py\n{trace_snippet}\n```",
                "inline": False
            })

        payload = {
            "username": "JOYST INCIDENT GUARDIAN",
            "avatar_url": "https://joystauth.cc/static/img/joyst_logo.png",
            "embeds": [
                {
                    "title": "🚨 [INCIDENT DETECTED] Server Glitch / Exception Intercepted",
                    "description": "An automated telemetry event was triggered. The server handled the error and protected sensitive memory.",
                    "color": 0xEF4444,
                    "fields": fields,
                    "footer": {
                        "text": "JOYST SHIELD AUTO-INCIDENT GUARDIAN • Zero-Downtime Telemetry"
                    },
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
            ]
        }
        try:
            requests.post(target_webhook, json=payload, timeout=3)
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()

def send_discord_system_lifecycle_alert(event_type: str, details: str = ""):
    """Dispatches clean operational status embeds (Online, Restart, Recovery)."""
    target_webhook = os.getenv("INCIDENT_DISCORD_WEBHOOK_URL", DEFAULT_DISCORD_WEBHOOK_URL)
    if not target_webhook or not target_webhook.startswith("http"):
        return

    import threading
    def _post():
        is_online = event_type == "STARTUP" or event_type == "ONLINE"
        color = 0x10B981 if is_online else 0xF59E0B
        title = "🟢 [SYSTEM ONLINE] Joyst Auth Core Operational" if is_online else f"⚠️ [SYSTEM NOTICE] {event_type}"

        payload = {
            "username": "JOYST SYSTEM TELEMETRY",
            "avatar_url": "https://joystauth.cc/static/img/joyst_logo.png",
            "embeds": [
                {
                    "title": title,
                    "description": details or "Server instance initialized and connected to database backend successfully.",
                    "color": color,
                    "fields": [
                        {"name": "🚀 Platform Version", "value": f"`v{PLATFORM_VERSION}`", "inline": True},
                        {"name": "🛡️ Security Engine", "value": "`AES-256 Active`", "inline": True},
                        {"name": "⏱️ Timestamp", "value": f"<t:{int(datetime.datetime.utcnow().timestamp())}:R>", "inline": True}
                    ],
                    "footer": {"text": "JOYST CLOUD INFRASTRUCTURE MONITOR"},
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
            ]
        }
        try:
            requests.post(target_webhook, json=payload, timeout=3)
        except Exception:
            pass

    threading.Thread(target=_post, daemon=True).start()
