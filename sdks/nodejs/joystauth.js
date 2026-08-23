/**
 * JOYST CORPORATION AUTH - Node.js / Electron Standalone SDK
 * Pure vanilla Node.js (crypto + https/http) with zero external npm dependencies!
 */

const crypto = require('crypto');
const http = require('http');
const https = require('https');
const os = require('os');

class JoystAuth {
    constructor(name, token, version = "1.0", url = "https://joystauth.cc") {
        this.name = name;
        this.token = token;
        this.version = version;
        this.url = (url || "https://joystauth.cc").replace(/\/$/, "");
        this.sessionid = null;
        this.enckey = null;
        this.hwid = this.getHwid();
        this.userData = {};
        this.response = { success: false, message: "" };
        this.notifications = [];
    }

    getHwid() {
        const raw = `${os.hostname()}-${os.platform()}-${os.arch()}-${os.cpus()[0]?.model || ''}`;
        return crypto.createHash('sha256').update(raw.toUpperCase()).digest('hex');
    }

    deriveKey(token) {
        return crypto.createHash('sha256').update(token).digest();
    }

    decryptAes(cipherBase64, keyStr) {
        const key = this.deriveKey(keyStr);
        const raw = Buffer.from(cipherBase64, 'base64');
        const iv = raw.slice(0, 16);
        const encrypted = raw.slice(16);
        const decipher = crypto.createDecipheriv('aes-256-cbc', key, iv);
        let decrypted = decipher.update(encrypted);
        decrypted = Buffer.concat([decrypted, decipher.final()]);
        return decrypted.toString('utf8');
    }

    encryptAes(plainText, keyStr) {
        const key = this.deriveKey(keyStr);
        const iv = crypto.randomBytes(16);
        const cipher = crypto.createCipheriv('aes-256-cbc', key, iv);
        let encrypted = cipher.update(Buffer.from(plainText, 'utf8'));
        encrypted = Buffer.concat([encrypted, cipher.final()]);
        return Buffer.concat([iv, encrypted]).toString('base64');
    }

    async postJson(endpoint, data) {
        return new Promise((resolve) => {
            const urlObj = new URL(`${this.url}${endpoint}`);
            const body = JSON.stringify(data);
            const isHttps = urlObj.protocol === 'https:';
            const client = isHttps ? https : http;

            const req = client.request({
                hostname: urlObj.hostname,
                port: urlObj.port || (isHttps ? 443 : 80),
                path: urlObj.pathname,
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Content-Length': Buffer.byteLength(body)
                }
            }, (res) => {
                let chunks = '';
                res.on('data', d => chunks += d);
                res.on('end', () => {
                    try {
                        resolve(JSON.parse(chunks));
                    } catch (e) {
                        resolve({ success: false, message: chunks });
                    }
                });
            });

            req.on('error', (err) => resolve({ success: false, message: err.message }));
            req.write(body);
            req.end();
        });
    }

    async init() {
        const res = await this.postJson('/api/v1/client/init', {
            name: this.name,
            token: this.token,
            version: this.version,
            hwid: this.hwid
        });

        if (res.success) {
            this.sessionid = res.sessionid;
            this.enckey = this.decryptAes(res.enckey, this.token);
            this.response = { success: true, message: "Initialized successfully" };
            this.notifications = res.notifications || [];
            
            // Auto-start watchdog heartbeat
            this.startWatchdog(15);
            return true;
        } else {
            const msg = res.message || "Init failed";
            this.response = { success: false, message: msg };

            // Inbuilt Automatic Maintenance Killswitch
            if (msg.toLowerCase().includes("maintenance") || res.is_maintenance) {
                console.error("\n🚨 [EMERGENCY MAINTENANCE ACTIVE] " + msg);
                console.error("❌ Application execution forcefully terminated by developer.");
                process.exit(0);
            }

            return false;
        }
    }

    async sendAction(payloadData) {
        if (!this.sessionid) {
            const ok = await this.init();
            if (!ok) return false;
        }

        const encPayload = this.encryptAes(JSON.stringify({ ...payloadData, hwid: this.hwid }), this.enckey);
        const res = await this.postJson('/api/v1/client/gateway', {
            sessionid: this.sessionid,
            data: encPayload
        });

        if (res.data) {
            const decrypted = JSON.parse(this.decryptAes(res.data, this.enckey));
            this.response = { success: decrypted.success, message: decrypted.message || "" };
            if (decrypted.success && decrypted.info) {
                this.userData = decrypted.info;
            }
            return decrypted.success;
        } else {
            this.response = { success: false, message: res.message || "Request failed" };
            return false;
        }
    }

    async login(username, password) {
        return this.sendAction({ type: "login", username, password });
    }

    async register(username, password, key) {
        return this.sendAction({ type: "register", username, password, key });
    }

    async license(key) {
        return this.sendAction({ type: "license", key });
    }

    async var(varid) {
        await this.sendAction({ type: "var", varid });
        return this.response.message;
    }

    async check() {
        return this.sendAction({ type: "check" });
    }

    startWatchdog(intervalSeconds = 15) {
        setInterval(async () => {
            if (!this.sessionid) return;
            const valid = await this.check();
            if (!valid && this.response.message.toLowerCase().includes("maintenance")) {
                console.error("\n🚨 [EMERGENCY MAINTENANCE ACTIVE] " + this.response.message);
                process.exit(0);
            }
        }, intervalSeconds * 1000);
    }
}

module.exports = JoystAuth;
