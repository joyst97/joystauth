const https = require('https');
const http = require('http');
const crypto = require('crypto');
const os = require('os');

class JoystAuth {
    constructor(name, token, version = "1.0", url = "https://joystauth.cc") {
        this.name = name;
        this.token = token;
        this.version = version;
        this.url = (url || "https://joystauth.cc").replace(/\/+$/, '');
        this.sessionid = null;
        this.hwid = crypto.createHash('sha256').update(os.hostname() + os.userInfo().username).digest('hex');
        this.userData = { username: "", subscription: "default", expiry: "Lifetime", hwid: this.hwid };
        this.response = { success: false, message: "" };

        // ⚡ 1. Inbuilt Auto-Init
        this.init(true);

        // ⚡ 2. Inbuilt Live Heartbeat Watchdog
        this.startHeartbeatWatchdog();
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
        }, 3000);
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
            this.userData.username = res.username;
            this.userData.subscription = res.subscription || "default";
            this.userData.expiry = res.expires_at || "Lifetime";
            this.response = { success: true, message: res.message || "License verified" };
            return true;
        } else {
            this.response = { success: false, message: res.message || res.detail || "Invalid license key." };
            return false;
        }
    }
}

module.exports = JoystAuth;
