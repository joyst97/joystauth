import os
import sys
import json
import re
import subprocess
import threading
import time
import requests

class UserData:
    def __init__(self, username="", subscription="", expiry="", hwid="", ip=""):
        self.username = username
        self.subscription = subscription
        self.expiry = expiry
        self.expires = expiry
        self.hwid = hwid
        self.ip = ip

class ResponseData:
    def __init__(self, success=False, message="", is_maintenance=False, active_notification=""):
        self.success = success
        self.message = message
        self.is_maintenance = is_maintenance
        self.active_notification = active_notification

class JoystAuth:
    """
    Joyst Corporation Auth Python SDK (100% Zero-Boilerplate Autopilot)
    """
    def __init__(self, name: str, token: str, version: str = "1.0", url: str = "https://joystauth.cc"):
        self.name = name
        self.token = token
        self.version = version
        self.url = (url or "https://joystauth.cc").rstrip("/")
        
        self.sessionid = None
        self.is_initialized = False
        self.hwid = self._get_hwid()
        self.user_data = UserData()
        self.response = ResponseData()
        self._last_notification = ""

        # ⚡ 1. Auto-init on launch
        self.init(auto_exit_on_maint=True)

        # ⚡ 2. Auto-launch background real-time heartbeat watchdog
        self._start_heartbeat_watchdog()

    def _get_hwid(self) -> str:
        hwid_str = ""
        try:
            if sys.platform == "win32":
                # Get Windows User Account SID (KeyAuth format S-1-5-21-...)
                out = subprocess.check_output("whoami /user", shell=True, stderr=subprocess.DEVNULL).decode().strip()
                m = re.search(r'S-1-5-21-\d+-\d+-\d+-\d+', out)
                if m:
                    return m.group(0)
                # Fallback: wmic csproduct get uuid
                output = subprocess.check_output("wmic csproduct get uuid", shell=True, stderr=subprocess.DEVNULL).decode().strip()
                lines = [l.strip() for l in output.split("\n") if l.strip() and "UUID" not in l]
                if lines: return lines[0]
            if not hwid_str:
                import uuid
                hwid_str = str(uuid.getnode())
        except Exception:
            import uuid
            hwid_str = str(uuid.getnode())
        return hwid_str

    def init(self, auto_exit_on_maint: bool = True) -> bool:
        try:
            payload = {"app_name": self.name, "app_token": self.token, "version": self.version, "hwid": self.hwid}
            res = requests.post(f"{self.url}/api/v1/client/init", json=payload, timeout=8)
            data = res.json()

            if data.get("success"):
                self.sessionid = data.get("sessionid")
                self.is_initialized = True
                self.response.success = True
                self.response.message = data.get("message", "Initialized successfully")
                self.response.is_maintenance = False

                notifs = data.get("notifications", [])
                if notifs and auto_exit_on_maint:
                    n = notifs[0]
                    self._last_notification = f"{n.get('title', 'ANNOUNCEMENT')}\n{n.get('message', '')}"
                    print(f"\n📢 [JOYST NOTIFICATION] {n.get('title')}: {n.get('message')}\n")
                return True
            else:
                self.response.success = False
                self.response.message = data.get("message") or data.get("detail") or "Failed to connect to authentication server."
                self.response.is_maintenance = bool(data.get("is_maintenance"))

                if auto_exit_on_maint:
                    print(f"\n🚨 [JOYST ALERT] {self.response.message}\n")
                    sys.exit(1)
                return False
        except Exception as e:
            self.response.success = False
            self.response.message = f"Connection error: {str(e)}"
            return False

    def _start_heartbeat_watchdog(self):
        def _loop():
            while True:
                time.sleep(15)
                if not self.sessionid: continue
                try:
                    payload = {
                        "app_name": self.name,
                        "app_token": self.token,
                        "hwid": self.hwid,
                        "username": self.user_data.username,
                        "sessionid": self.sessionid
                    }
                    res = requests.post(f"{self.url}/api/v1/client/check", json=payload, timeout=5)
                    if res.status_code == 200:
                        d = res.json()
                        if not d.get("success"):
                            msg = d.get("message", "Application placed into maintenance mode.")
                            print(f"\n🚨 [JOYST SECURITY ALERT] {msg}\n")
                            os._exit(1)
                except Exception:
                    pass
        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def login(self, username: str, password: str) -> bool:
        try:
            payload = {
                "app_name": self.name,
                "app_token": self.token,
                "username": username.strip(),
                "password": password,
                "hwid": self.hwid,
                "sessionid": self.sessionid
            }
            res = requests.post(f"{self.url}/api/v1/client/login", json=payload, timeout=8)
            data = res.json()

            if data.get("success"):
                self.user_data.username = username
                self.user_data.subscription = data.get("subscription", "default")
                self.user_data.expiry = data.get("expires_at", "Lifetime")
                self.user_data.hwid = self.hwid
                self.response.success = True
                self.response.message = data.get("message", "Logged in successfully")
                return True
            else:
                self.response.success = False
                self.response.message = data.get("message", "Login failed")
                return False
        except Exception as e:
            self.response.success = False
            self.response.message = str(e)
            return False

    def license(self, key: str) -> bool:
        try:
            payload = {
                "app_name": self.name,
                "app_token": self.token,
                "license_key": key.strip(),
                "hwid": self.hwid,
                "sessionid": self.sessionid
            }
            res = requests.post(f"{self.url}/api/v1/client/license", json=payload, timeout=8)
            data = res.json()

            if data.get("success"):
                self.user_data.username = data.get("username", key)
                self.user_data.subscription = data.get("subscription", "VIP Tier")
                self.user_data.expiry = data.get("expires_at", "Lifetime")
                self.user_data.hwid = self.hwid
                self.response.success = True
                self.response.message = data.get("message", "License verified successfully")
                return True
            else:
                self.response.success = False
                self.response.message = data.get("message", "Invalid license key")
                return False
        except Exception as e:
            self.response.success = False
            self.response.message = str(e)
            return False

    def register(self, username: str, password: str, license_key: str) -> bool:
        try:
            payload = {
                "app_name": self.name,
                "app_token": self.token,
                "username": username.strip(),
                "password": password,
                "license_key": license_key.strip(),
                "hwid": self.hwid,
                "sessionid": self.sessionid
            }
            res = requests.post(f"{self.url}/api/v1/client/register", json=payload, timeout=8)
            data = res.json()

            if data.get("success"):
                self.user_data.username = username
                self.response.success = True
                self.response.message = data.get("message", "Registered successfully")
                return True
            else:
                self.response.success = False
                self.response.message = data.get("message", "Registration failed")
                return False
        except Exception as e:
            self.response.success = False
            self.response.message = str(e)
            return False

    def var(self, var_name: str) -> str:
        try:
            payload = {
                "app_name": self.name,
                "app_token": self.token,
                "var_name": var_name,
                "sessionid": self.sessionid
            }
            res = requests.post(f"{self.url}/api/v1/client/var", json=payload, timeout=8)
            data = res.json()
            return data.get("value", "")
        except Exception:
            return ""
