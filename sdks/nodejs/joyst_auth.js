/**
 * JOYST CORPORATION AUTH - Node.js / Electron Standalone SDK
 * Pure vanilla Node.js (crypto + https/http) with zero external npm dependencies!
 */

const crypto = require('crypto');
const http = require('http');
const https = require('https');
const os = require('os');

class JoystAuth {
    constructor(name, ownerid, secret, version = "1.0", url = "http://127.0.0.1:8000") {
        this.name = name;
        this.ownerid = ownerid;
        this.secret = secret;
        this.version = version;
        this.url = url.replace(/\/$/, "");
        this.sessionid = null;
        this.enckey = null;
        this.hwid = this.getHwid();
        this.userData = {};
        this.response = { success: false, message: "" };
    }

    getHwid() {
        const raw = `${os.hostname()}-${os.platform()}-${os.arch()}-${os.cpus()[0]?.model || ''}`;
        return crypto.createHash('sha256').update(raw.toUpperCase()).digest('hex');
    }

    deriveKey(secret) {
        return crypto.createHash('sha256').update(secret).digest();
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
        return new Promise((resolve, reject) => {
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
            ownerid: this.ownerid,
            secret: this.secret,
            version: this.version,
            hwid: this.hwid
        });

        if (res.success) {
            this.sessionid = res.sessionid;
            this.enckey = this.decryptAes(res.enckey, this.secret);
            return true;
        } else {
            this.response = { success: false, message: res.message || "Init failed" };
            return false;
        }
    }

    async login(username, password) {
        if (!this.sessionid) await this.init();

        const payload = JSON.stringify({
            type: "login",
            username: username,
            pass: password,
            hwid: this.hwid,
            sessionid: this.sessionid,
            name: this.name,
            ownerid: this.ownerid
        });

        const encrypted = this.encryptAes(payload, this.enckey);
        const res = await this.postJson('/api/v1/client/gateway', {
            sessionid: this.sessionid,
            data: encrypted
        });

        if (res.success && res.data) {
            const dec = JSON.parse(this.decryptAes(res.data, this.enckey));
            this.response = { success: dec.success, message: dec.message };
            if (dec.success && dec.info) {
                this.userData = dec.info;
                return true;
            }
        }
        this.response = { success: false, message: res.message || "Login failed" };
        return false;
    }

    async license(licenseKey) {
        if (!this.sessionid) await this.init();

        const payload = JSON.stringify({
            type: "license",
            key: licenseKey,
            hwid: this.hwid,
            sessionid: this.sessionid,
            name: this.name,
            ownerid: this.ownerid
        });

        const encrypted = this.encryptAes(payload, this.enckey);
        const res = await this.postJson('/api/v1/client/gateway', {
            sessionid: this.sessionid,
            data: encrypted
        });

        if (res.success && res.data) {
            const dec = JSON.parse(this.decryptAes(res.data, this.enckey));
            this.response = { success: dec.success, message: dec.message };
            if (dec.success && dec.info) {
                this.userData = dec.info;
                return true;
            }
        }
        this.response = { success: false, message: res.message || "License check failed" };
        return false;
    }
}

module.exports = JoystAuth;
