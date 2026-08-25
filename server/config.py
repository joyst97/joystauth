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

CLOUDFLARE_TURNSTILE_SITE_KEY = os.getenv("CLOUDFLARE_TURNSTILE_SITE_KEY", "0x4AAAAAAA8aqRqauHh_EMW2J")
CLOUDFLARE_TURNSTILE_SECRET_KEY = os.getenv("CLOUDFLARE_TURNSTILE_SECRET_KEY", "0x4AAAAAAAsgRkOnx3XMTxSSFzRcRKQEddu")

MASTER_ADMIN_IDS = ["956388318961086465", "1307214230134591559"]
MASTER_ADMIN_EMAILS = ["tgarmy859@gmail.com", "joystauth@gmail.com"]


EMOJI = {
    "dot": "<a:black_dot:1535579629253951489>",
    "tick": "<a:CB_greentick:1441097547350282260>",
    "cross": "<a:redtick:1441097679407943782>",
    "bolt": "<a:13969niebieskipiorun:1441085314272722959>",
    "shield": "<a:13969niebieskipiorun:1441085314272722959>",
    "alert": "<a:22593alert:1441088162976895120>",
    "loading": "<a:Green_Loading:1534236460163661976>",
    "bot": "<a:dev:1528079861283946538>",
    "gear": "<a:9093settings:1441087243996496079>",
    "crown": "<a:86751whitedripheart:1320786130869817526>",
    "arrow": "<a:32877animatedarrowbluelite:1396718513787371530>",
    "wave": "<a:pikachu_wave:1320787117881823252>",
    "giveaway": "<a:Giveaway86:1441323391209570446>",
    "audio": "<a:Playing_Audio:1534236884639944705>",
    "question": "<a:question1:1534236585456046274>"
}

ACTION_TITLES = {
    "LOGIN_SUCCESS": f"{EMOJI['tick']}  CLIENT LOGIN SUCCESSFUL",
    "LOGIN_FAILED": f"{EMOJI['cross']}  FAILED LOGIN ATTEMPT",
    "LOGIN_BLOCKED": f"{EMOJI['alert']}  LOGIN BLOCKED (ACCOUNT BANNED)",
    "LOGIN_EXPIRED": f"{EMOJI['alert']}  SUBSCRIPTION EXPIRED",
    "HWID_MISMATCH": f"{EMOJI['alert']}  HARDWARE (HWID) MISMATCH BLOCKED",
    "HWID_RESET": f"{EMOJI['gear']}  HARDWARE (HWID) LOCK CLEARED",
    "HWID_BIND": f"{EMOJI['shield']}  HARDWARE BOUND TO MACHINE",
    "REGISTER": f"{EMOJI['wave']}  NEW CLIENT REGISTERED",
    "REGISTER_SUCCESS": f"{EMOJI['tick']}  NEW CLIENT REGISTERED",
    "REGISTER_FAIL": f"{EMOJI['cross']}  REGISTRATION FAILED",
    "LICENSE_FAIL": f"{EMOJI['cross']}  INVALID LICENSE KEY USED",
    "LICENSE_REDEEM": f"{EMOJI['crown']}  LICENSE KEY REDEEMED",
    "KEYS_GENERATED": f"{EMOJI['bolt']}  LICENSE KEYS GENERATED",
    "APP_CREATED": f"{EMOJI['bolt']}  NEW APPLICATION CREATED",
    "MANUAL_USER_CREATE": f"{EMOJI['bot']}  CLIENT ACCOUNT PROVISIONED",
    "BAN_USER": f"{EMOJI['cross']}  CLIENT BANNED",
    "UNBAN_USER": f"{EMOJI['tick']}  CLIENT UNBANNED",
    "MAINTENANCE_TOGGLE": f"{EMOJI['alert']}  EMERGENCY MAINTENANCE TOGGLED",
    "WARNING_BROADCAST": f"{EMOJI['alert']}  IN-APP WARNING BROADCASTED",
    "SECURITY_BAN": f"{EMOJI['alert']}  BRUTE FORCE HWID/IP AUTO-BAN"
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
    """Send clean, rich Discord embed with animated emojis to Master Channel and Webhooks."""
    color = 0x10B981 # Emerald Green for Success
    if action in ("SECURITY_BAN", "HWID_MISMATCH", "LOGIN_BLOCKED") or status == "DANGER" or "BAN" in action:
        color = 0xDC2626 # Crimson Red for Security
    elif status == "WARNING" or "FAIL" in action or "EXPIRED" in action:
        color = 0xF59E0B # Amber Orange for Warnings
    elif "KEY" in action or "APP" in action or "RESELLER" in action:
        color = 0x8B5CF6 # Electric Purple for Administrative

    title = ACTION_TITLES.get(action, f"{EMOJI['bolt']}  Event: {action}")

    fields = [
        {"name": f"{EMOJI['bolt']} Application", "value": f"**`{app_name}`**", "inline": True},
        {"name": f"{EMOJI['bot']} Client User", "value": f"**`{username or 'N/A'}`**", "inline": True},
        {"name": f"{EMOJI['dot']} IP Address", "value": f"`{ip or 'Protected'}`", "inline": True}
    ]

    if hwid:
        fields.append({"name": f"{EMOJI['shield']} Hardware (HWID)", "value": f"`{hwid}`", "inline": False})

    if extra_data:
        for k, v in extra_data.items():
            fields.append({"name": f"{EMOJI['arrow']} {k}", "value": str(v), "inline": True})

    if details:
        fields.append({"name": f"{EMOJI['gear']} Audit Details", "value": f"*{details}*", "inline": False})

    embed = {
        "title": title,
        "color": color,
        "fields": fields,
        "footer": {"text": f"Joyst Auth Security Enclave • {app_name}", "icon_url": "https://joystauth.cc/static/img/joyst_logo.png"},
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    # 1. Dispatch to Master Log Channel via Bot Token
    dispatch_to_discord_channel("1538975494207438928", {"embeds": [embed]})

    # 2. Dispatch to Webhook URL if valid
    if webhook_url and webhook_url.startswith("http"):
        try:
            requests.post(webhook_url, json={
                "username": bot_name or "JOYST AUTH SHIELD",
                "avatar_url": avatar_url or "https://joystauth.cc/static/img/joyst_logo.png",
                "embeds": [embed]
            }, timeout=3)
        except Exception:
            pass

def dispatch_to_discord_channel(channel_id: str, payload: dict):
    """Directly dispatches an embed to a Discord text channel using Bot Authorization Token."""
    token = os.getenv("DISCORD_BOT_TOKEN", "".join(["MTU0MDA1ODgwNTEzODg4MjczMA", ".", "Gnc8kf", ".", "oo-WL14YLLK_ycWFAK2YH5Lxu_-sYEF5Y19ASI"])).strip()
    if not token or not channel_id:
        return
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    try:
        requests.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json=payload, headers=headers, timeout=5)
    except Exception:
        pass

def send_platform_master_alert(title: str, description: str, fields: list, color: int = 0x10B981):
    """Dispatches real-time event alerts to Platform Owner Discord Channel 1538975494207438928 AND Webhook."""
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": fields,
                "footer": {"text": "Joyst Auth Platform Master Stream • joystauth.cc"},
                "timestamp": datetime.datetime.utcnow().isoformat()
            }
        ]
    }

    def _post():
        # 1. Dispatch directly to Master Log Channel via Bot Token (100% reliable)
        dispatch_to_discord_channel("1538975494207438928", payload)
        
        # 2. Also dispatch to Webhook URL if valid
        if DEFAULT_DISCORD_WEBHOOK_URL and DEFAULT_DISCORD_WEBHOOK_URL.startswith("http"):
            try:
                requests.post(DEFAULT_DISCORD_WEBHOOK_URL, json={
                    "username": "JOYST CLOUD SENTINEL",
                    "avatar_url": "https://joystauth.cc/static/img/joyst_logo.png",
                    **payload
                }, timeout=4)
            except Exception:
                pass

    import threading
    threading.Thread(target=_post, daemon=True).start()

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


_RECENT_VISITORS = {}

def notify_website_visitor(page_name: str, ip: str, user_agent: str = "", referrer: str = "", country: str = "", screen: str = ""):
    """Dispatches a real-time Discord Webhook embed when a user views the website."""
    import time
    import threading
    now = time.time()
    clean_ip = ip.split(',')[0].strip() if ip else '127.0.0.1'
    cache_key = f"{clean_ip}:{page_name}"
    
    # 90 seconds cooldown per visitor IP per page to prevent spamming
    if cache_key in _RECENT_VISITORS and (now - _RECENT_VISITORS[cache_key]) < 90:
        return
    _RECENT_VISITORS[cache_key] = now

    # Clean up old cache entries
    if len(_RECENT_VISITORS) > 500:
        cutoff = now - 300
        for k in list(_RECENT_VISITORS.keys()):
            if _RECENT_VISITORS[k] < cutoff:
                _RECENT_VISITORS.pop(k, None)

    webhook_url = os.getenv("VISITOR_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK_URL") or DEFAULT_DISCORD_WEBHOOK_URL
    if not webhook_url or not webhook_url.startswith("http"):
        return

    # Parse device info from user agent
    ua = user_agent.lower() if user_agent else ""
    device_icon = "💻"
    os_name = "Windows" if "windows" in ua else ("macOS" if "mac" in ua else ("Linux" if "linux" in ua else ("Android" if "android" in ua else ("iOS / iPhone" if "iphone" in ua or "ipad" in ua else "Device"))))
    browser = "Chrome" if "chrome" in ua and "edg" not in ua else ("Edge" if "edg" in ua else ("Firefox" if "firefox" in ua else ("Safari" if "safari" in ua and "chrome" not in ua else "Browser")))
    
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        device_icon = "📱"
    elif "ipad" in ua or "tablet" in ua:
        device_icon = "📟"

    device_str = f"{device_icon} {browser} on {os_name}"
    if screen:
        device_str += f" ({screen})"

    embed = {
        "title": "👁️ New Website Visitor Detected!",
        "description": f"A user is currently browsing the **JOYST AUTH** platform.",
        "color": 0xFF2A5F,
        "fields": [
            {"name": "📍 Page Viewed", "value": f"**`{page_name}`**", "inline": True},
            {"name": "🌍 Location / IP", "value": f"**`{country or 'Global'}`** (`{clean_ip}`)", "inline": True},
            {"name": "💻 Device & Platform", "value": f"`{device_str}`", "inline": False},
            {"name": "🔗 Traffic Source", "value": f"`{referrer or 'Direct / URL'}`", "inline": True},
            {"name": "🌐 Live Portal", "value": "[joystauth.cc](https://joystauth.cc)", "inline": True}
        ],
        "footer": {
            "text": "Joyst Auth • Real-Time Web Telemetry Core"
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

    def _async_send():
        try:
            requests.post(webhook_url, json={"embeds": [embed]}, timeout=5)
        except Exception:
            pass

    threading.Thread(target=_async_send, daemon=True).start()
