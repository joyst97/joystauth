using System;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Collections.Generic;

namespace JoystAuth
{
    public class UserData
    {
        [JsonPropertyName("username")] public string username { get; set; } = "";
        [JsonPropertyName("subscription")] public string subscription { get; set; } = "default";
        [JsonPropertyName("expires_at")] public string expiry { get; set; } = "Lifetime";
        [JsonPropertyName("hwid")] public string hwid { get; set; } = "";
        [JsonPropertyName("ip")] public string ip { get; set; } = "";
    }

    public class ResponseData
    {
        [JsonPropertyName("success")] public bool success { get; set; }
        [JsonPropertyName("message")] public string message { get; set; } = "";
        [JsonPropertyName("is_maintenance")] public bool is_maintenance { get; set; }
    }

    public class api
    {
        public string name { get; set; }
        public string token { get; set; }
        public string version { get; set; }
        public string url { get; set; }
        public string sessionid { get; set; } = "";
        public string hwid { get; set; } = "";
        public UserData user_data { get; set; } = new UserData();
        public ResponseData response { get; set; } = new ResponseData();

        private static readonly HttpClient client = new HttpClient();
        private string lastNotification = "";

        [DllImport("user32.dll", CharSet = CharSet.Auto)]
        private static extern int MessageBox(IntPtr hWnd, String text, String caption, uint type);

        public api(string name, string token, string version = "1.0", string url = "https://joystauth.cc")
        {
            this.name = name;
            this.token = token;
            this.version = version;
            this.url = (url ?? "https://joystauth.cc").TrimEnd('/');
            this.hwid = GetHWID();

            // ⚡ 1. Inbuilt Auto-Init
            this.init(true);

            // ⚡ 2. Inbuilt Live Heartbeat Watchdog
            this.StartHeartbeatWatchdog();
        }

        private string GetHWID()
        {
            try
            {
                string mName = Environment.MachineName + Environment.UserName;
                using var sha = SHA256.Create();
                byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(mName));
                return Convert.ToHexString(hash);
            }
            catch { return "HWID_UNKNOWN"; }
        }

        public bool init(bool autoExitOnMaint = true)
        {
            try
            {
                var payload = new { app_name = this.name, app_token = this.token, version = this.version, hwid = this.hwid };
                var json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var res = client.PostAsync($"{this.url}/api/v1/client/init", content).GetAwaiter().GetResult();
                var resStr = res.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                bool ok = root.TryGetProperty("success", out var s) && s.GetBoolean();
                if (ok)
                {
                    this.sessionid = root.TryGetProperty("sessionid", out var sid) ? sid.GetString() : "";
                    this.response.success = true;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Initialized";
                    return true;
                }
                else
                {
                    this.response.success = false;
                    string msg = root.TryGetProperty("message", out var m) ? m.GetString() : (root.TryGetProperty("detail", out var d) ? d.GetString() : "Connection failed");
                    this.response.message = msg;
                    bool isMaint = root.TryGetProperty("is_maintenance", out var im) && im.GetBoolean();
                    this.response.is_maintenance = isMaint;

                    if (autoExitOnMaint)
                    {
                        MessageBox(IntPtr.Zero, msg, isMaint ? "JOYST - APPLICATION MAINTENANCE" : "JOYST - ACCESS BLOCKED", 0x30 | 0x40000);
                        Environment.Exit(0);
                    }
                    return false;
                }
            }
            catch (Exception ex)
            {
                this.response.success = false;
                this.response.message = ex.Message;
                return false;
            }
        }

        private void StartHeartbeatWatchdog()
        {
            new Thread(() =>
            {
                while (true)
                {
                    Thread.Sleep(3000);
                    try
                    {
                        var payload = new { app_name = this.name, app_token = this.token, hwid = this.hwid, username = this.user_data.username, sessionid = this.sessionid };
                        var json = JsonSerializer.Serialize(payload);
                        var content = new StringContent(json, Encoding.UTF8, "application/json");
                        var res = client.PostAsync($"{this.url}/api/v1/client/check", content).GetAwaiter().GetResult();
                        var resStr = res.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                        using var doc = JsonDocument.Parse(resStr);
                        var root = doc.RootElement;

                        if (root.TryGetProperty("success", out var s) && !s.GetBoolean())
                        {
                            string msg = root.TryGetProperty("message", out var m) ? m.GetString() : "Application placed into maintenance mode.";
                            MessageBox(IntPtr.Zero, msg, "JOYST - SECURITY ALERT", 0x30 | 0x40000);
                            Environment.Exit(0);
                        }
                    }
                    catch { }
                }
            })
            { IsBackground = true }.Start();
        }

        public bool license(string key)
        {
            try
            {
                var payload = new { app_name = this.name, app_token = this.token, license_key = key.Trim(), hwid = this.hwid, sessionid = this.sessionid };
                var json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var res = client.PostAsync($"{this.url}/api/v1/client/license", content).GetAwaiter().GetResult();
                var resStr = res.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                bool ok = root.TryGetProperty("success", out var s) && s.GetBoolean();
                if (ok)
                {
                    this.user_data.username = root.TryGetProperty("username", out var un) ? un.GetString() : "";
                    this.user_data.subscription = root.TryGetProperty("subscription", out var sub) ? sub.GetString() : "default";
                    this.user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() : "Lifetime";
                    this.user_data.ip = root.TryGetProperty("ip", out var ip) ? ip.GetString() : "";
                    this.response.success = true;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "License Verified";
                    return true;
                }
                else
                {
                    this.response.success = false;
                    this.response.message = root.TryGetProperty("message", out var m) ? m.GetString() : (root.TryGetProperty("detail", out var d) ? d.GetString() : "Invalid license key.");
                    return false;
                }
            }
            catch (Exception ex)
            {
                this.response.success = false;
                this.response.message = ex.Message;
                return false;
            }
        }
    }
}
