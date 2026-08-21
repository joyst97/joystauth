import os
import sys
import json
import base64
import hashlib
import subprocess
import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

class UserData:
    def __init__(self, username="", subscription="", expiry="", hwid="", ip="", created_date=""):
        self.username = username
        self.subscription = subscription
        self.expires = expiry
        self.expiry = expiry
        self.hwid = hwid
        self.ip = ip
        self.created_date = created_date

class ResponseData:
    def __init__(self, success=False, message=""):
        self.success = success
        self.message = message

class api:
    """
    Joyst Corporation Auth API Client (Exact KeyAuth parity)
    """
    def __init__(self, name: str, ownerid: str, secret: str, version: str = "1.0", url: str = "http://127.0.0.1:8000"):
        self.name = name
        self.ownerid = ownerid
        self.secret = secret
        self.version = version
        self.url = url.rstrip("/")
        
        self.sessionid = None
        self.enckey = None
        self.is_initialized = False
        self.hwid = self._get_hwid()
        self.user_data = UserData()
        self.response = ResponseData()

    def _get_hwid(self) -> str:
        """Extract Hardware ID from computer."""
        hwid_str = ""
        try:
            if sys.platform == "win32":
                cmd = "wmic csproduct get uuid"
                output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
                lines = [line.strip() for line in output.split("\n") if line.strip() and "UUID" not in line]
                if lines:
                    hwid_str = lines[0]
            if not hwid_str:
                import uuid
                hwid_str = str(uuid.getnode())
        except Exception:
            import uuid
            hwid_str = str(uuid.getnode())
        
        return hashlib.sha256(hwid_str.strip().upper().encode("utf-8")).hexdigest()

    def _derive_key(self, secret: str) -> bytes:
        return hashlib.sha256(secret.encode("utf-8")).digest()

    def _encrypt(self, plaintext: str, key_str: str) -> str:
        key = self._derive_key(key_str)
        iv = os.urandom(16)
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plaintext.encode("utf-8"), AES.block_size)
        encrypted = cipher.encrypt(padded)
        return base64.b64encode(iv + encrypted).decode("utf-8")

    def _decrypt(self, ciphertext_b64: str, key_str: str) -> str:
        key = self._derive_key(key_str)
        raw = base64.b64decode(ciphertext_b64.encode("utf-8"))
        iv = raw[:16]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted_padded = cipher.decrypt(raw[16:])
        return unpad(decrypted_padded, AES.block_size).decode("utf-8")

    def init(self) -> bool:
        """Initialize session with Joyst Auth Server."""
        try:
            payload = {
                "name": self.name,
                "ownerid": self.ownerid,
                "secret": self.secret,
                "version": self.version,
                "hwid": self.hwid
            }
            res = requests.post(f"{self.url}/api/v1/client/init", json=payload, timeout=8)
            data = res.json()

            if data.get("success"):
                self.sessionid = data.get("sessionid")
                # Decrypt session encryption key using app secret
                encrypted_key = data.get("enckey")
                self.enckey = self._decrypt(encrypted_key, self.secret)
                self.is_initialized = True
                self.response = ResponseData(True, "Initialized successfully")
                return True
            else:
                self.response = ResponseData(False, data.get("message", "Initialization failed"))
                return False
        except Exception as e:
            self.response = ResponseData(False, f"Connection failed: {str(e)}")
            return False

    def _send_action(self, action_type: str, **kwargs) -> bool:
        if not self.is_initialized:
            if not self.init():
                return False

        try:
            payload_data = {"type": action_type, "hwid": self.hwid, **kwargs}
            encrypted_payload = self._encrypt(json.dumps(payload_data), self.enckey)

            body = {
                "sessionid": self.sessionid,
                "data": encrypted_payload
            }
            res = requests.post(f"{self.url}/api/v1/client/gateway", json=body, timeout=8)
            res_json = res.json()

            if "data" in res_json:
                decrypted_res = self._decrypt(res_json["data"], self.enckey)
                parsed = json.loads(decrypted_res)
                success = parsed.get("success", False)
                message = parsed.get("message", "")

                if success and "info" in parsed:
                    info = parsed["info"]
                    self.user_data = UserData(
                        username=info.get("username", ""),
                        subscription=info.get("subscription", ""),
                        expiry=info.get("expiry", ""),
                        hwid=info.get("hwid", ""),
                        ip=info.get("ip", ""),
                        created_date=info.get("created_date", "")
                    )

                self.response = ResponseData(success, message)
                return success
            else:
                self.response = ResponseData(False, res_json.get("message", "Request failed"))
                return False
        except Exception as e:
            self.response = ResponseData(False, f"Error: {str(e)}")
            return False

    def start_heartbeat(self, interval_seconds: int = 30):
        """Starts background anti-tamper heartbeat thread to continuously validate session."""
        import threading
        import time

        def _watchdog():
            while True:
                time.sleep(interval_seconds)
                # Check for debuggers / hooks
                if sys.gettrace() is not None:
                    self._send_action("security_alert", reason="Python tracer/debugger attached", threat="Debugger")
                    os._exit(0)
                
                # Send server heartbeat ping
                ok = self._send_action("heartbeat")
                if not ok:
                    os._exit(0) # Session revoked or expired

        t = threading.Thread(target=_watchdog, daemon=True)
        t.start()

    def login(self, username: str, password: str) -> bool:
        """Login with username and password (HWID lock enforced)."""
        return self._send_action("login", username=username, password=password)

    def register(self, username: str, password: str, key: str) -> bool:
        """Register a new user account with a license key."""
        return self._send_action("register", username=username, password=password, key=key)

    def license(self, key: str) -> bool:
        """Login using license key only."""
        return self._send_action("license", key=key)

    def var(self, var_name: str) -> str:
        """Fetch remote encrypted cloud variable."""
        if self._send_action("var", varid=var_name):
            return self.response.message
        return ""

    def check(self) -> bool:
        """Check session validity."""
        return self._send_action("check")

    def log(self, message: str) -> bool:
        """Send custom message log to dashboard."""
        return self._send_action("log", message=message)

# Alias for backwards compatibility
AuthClient = api

