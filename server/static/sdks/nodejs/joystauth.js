const https = require('https');
const http = require('http');
const os = require('os');
const { execSync } = require('child_process');

class JoystAuth {
    constructor(name, token, version = "1.0", url = "https://joystauth.cc") {
        this.name = name;
        this.token = token;
        this.version = version;
        this.url = (url || "https://joystauth.cc").replace(/\/+$/, '');
        this.sessionid = null;
        this.hwid = this.getHWID();
        this.userData = { username: "", subscription: "default", expiry: "Lifetime", hwid: this.hwid };
        this.response = { success: false, message: "" };

        // ⚡ 1. Inbuilt Auto-Init
        this.init(true);

        // ⚡ 2. Inbuilt Live Heartbeat Watchdog
        this.startHeartbeatWatchdog();
    }

    getHWID() {
        try {
            if (process.platform === 'win32') {
                const out = execSync('whoami /user', { stdio: ['pipe', 'pipe', 'ignore'] }).toString();
                const match = out.match(/S-1-5-21-\d+-\d+-\d+-\d+/);
                if (match) return match[0];
            }
        } catch(e) {}
        return os.hostname() + "_" + os.userInfo().username;
    }

    _post(endpoint, data) {
        return new Promise((resolve) => {
            const urlObj = new URL(this.url + endpoint);
            const isHttps = urlObj.protocol === 'https:';
            const client = isHttps ? https : http;
            const body = JSON.stringify(data);

            const req = client.request(urlObj, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(body),
                    'User-Agent': 'JoystEnclave-Node/2.0'
                }
            }, (res) => {
                let chunks = '';
                res.on('data', c => chunks += c);
                res.on('end', () => {
                    try { resolve(JSON.parse(chunks)); }
                    catch(e) { resolve({ success: false, message: "Invalid JSON response" }); }
                });
            });

            req.on('error', (e) => resolve({ success: false, message: e.message }));
            req.write(body);
            req.end();
        });
    }

    async init(autoExitOnMaint = true) {
        const res = await this._post('/api/v1/client/init', {
            app_name: this.name,
            app_token: this.token,
            version: this.version,
            hwid: this.hwid
        });

        if (res.success) {
            this.sessionid = res.sessionid;
            this.response = { success: true, message: res.message || "Initialized" };
            return true;
        } else {
            const msg = res.message || res.detail || "Authentication server error.";
            this.response = { success: false, message: msg };
            if (autoExitOnMaint) {
                console.error(`\n🚨 [JOYST ALERT] ${msg}\n`);
                process.exit(1);
            }
            return false;
        }
    }

    startHeartbeatWatchdog() {
        setInterval(async () => {
            if (!this.sessionid) return;
            try {
                const res = await this._post('/api/v1/client/check', {
                    app_name: this.name,
                    app_token: this.token,
                    hwid: this.hwid,
                    username: this.userData.username,
                    sessionid: this.sessionid
                });
                if (res && res.success === false) {
                    console.error(`\n🚨 [JOYST SECURITY ALERT] ${res.message || "Application placed into maintenance."}\n`);
                    process.exit(1);
                }
            } catch(e) {}
        }, 15000);
    }

    async login(username, password) {
        const res = await this._post('/api/v1/client/login', {
            app_name: this.name,
            app_token: this.token,
            username: username.trim(),
            password: password,
            hwid: this.hwid,
            sessionid: this.sessionid
        });

        if (res.success) {
            this.userData.username = username;
            this.userData.subscription = res.subscription || "default";
            this.userData.expiry = res.expires_at || "Lifetime";
            this.response = { success: true, message: res.message || "Logged in" };
            return true;
        } else {
            this.response = { success: false, message: res.message || "Login failed" };
            return false;
        }
    }

    async license(key) {
        const res = await this._post('/api/v1/client/license', {
            app_name: this.name,
            app_token: this.token,
            license_key: key.trim(),
            hwid: this.hwid,
            sessionid: this.sessionid
        });

        if (res.success) {
            this.userData.username = res.username || key;
            this.userData.subscription = res.subscription || "VIP Tier";
            this.userData.expiry = res.expires_at || "Lifetime";
            this.response = { success: true, message: res.message || "License Active" };
            return true;
        } else {
            this.response = { success: false, message: res.message || "Invalid License" };
            return false;
        }
    }

    async register(username, password, licenseKey) {
        const res = await this._post('/api/v1/client/register', {
            app_name: this.name,
            app_token: this.token,
            username: username.trim(),
            password: password,
            license_key: licenseKey.trim(),
            hwid: this.hwid,
            sessionid: this.sessionid
        });

        if (res.success) {
            this.userData.username = username;
            this.response = { success: true, message: res.message || "Registered" };
            return true;
        } else {
            this.response = { success: false, message: res.message || "Registration failed" };
            return false;
        }
    }

    async var(varName) {
        const res = await this._post('/api/v1/client/var', {
            app_name: this.name,
            app_token: this.token,
            var_name: varName,
            sessionid: this.sessionid
        });
        return res.value || "";
    }
}

module.exports = JoystAuth;
