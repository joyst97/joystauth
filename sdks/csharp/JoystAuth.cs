using System;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Diagnostics;
using Microsoft.Win32;

namespace JoystAuth
{
    public class SecurityShield
    {
        public static bool CheckCheatEngineInstalled()
        {
            try
            {
                // 1. Process Check
                string[] ceProcs = { "cheatengine", "cheatengine-x86_64", "cheatengine-i386", "processhacker", "x64dbg", "x32dbg", "ida64", "dnspy" };
                foreach (var p in Process.GetProcesses())
                {
                    string pName = p.ProcessName.ToLower();
                    foreach (var cep in ceProcs)
                    {
                        if (pName.Contains(cep)) return true;
                    }
                }

                // 2. Registry Check
                string[] regKeys = { @"Software\Cheat Engine", @"SOFTWARE\Cheat Engine", @"SOFTWARE\WOW6432Node\Cheat Engine" };
                foreach (var rk in regKeys)
                {
                    using var k1 = Registry.CurrentUser.OpenSubKey(rk);
                    if (k1 != null) return true;
                    using var k2 = Registry.LocalMachine.OpenSubKey(rk);
                    if (k2 != null) return true;
                }

                // 3. Directory Check
                string[] dirs = {
                    @"C:\Program Files\Cheat Engine",
                    @"C:\Program Files (x86)\Cheat Engine",
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "Cheat Engine")
                };
                foreach (var d in dirs)
                {
                    if (Directory.Exists(d)) return true;
                }
            }
            catch { }
            return false;
        }
    }

    public class UserData
    {
        public string username { get; set; } = "";
        public string subscription { get; set; } = "default";
        public string expiry { get; set; } = "Lifetime";
        public string hwid { get; set; } = "";
        public string ip { get; set; } = "";
    }

    public class ResponseData
    {
        public bool success { get; set; } = false;
        public string message { get; set; } = "";
    }

    public class api
    {
        public string name { get; }
        public string token { get; }
        public string version { get; }
        public string url { get; }
        public string hwid { get; }
        public string sessionid { get; private set; } = "";

        public UserData user_data { get; } = new UserData();
        public ResponseData response { get; } = new ResponseData();

        private static readonly HttpClient client = new HttpClient { Timeout = TimeSpan.FromSeconds(8) };

        public api(string name, string token, string version = "1.0", string url = "https://joystauth.cc")
        {
            this.name = name;
            this.token = token;
            this.version = version;
            this.url = (url ?? "https://joystauth.cc").TrimEnd('/');
            this.hwid = GetHWID();

            if (SecurityShield.CheckCheatEngineInstalled())
            {
                Environment.Exit(0);
            }

            // ⚡ 1. Inbuilt Auto-Init
            this.init(true);

            // ⚡ 2. Inbuilt Live Heartbeat Watchdog
            this.StartHeartbeatWatchdog();
        }

        // Exact Windows User Account SID (KeyAuth format S-1-5-21-...)
        private string GetHWID()
        {
            try
            {
                var identity = WindowsIdentity.GetCurrent();
                if (identity?.User != null)
                {
                    return identity.User.Value;
                }
            }
            catch { }

            try
            {
                return Environment.MachineName + "_" + Environment.UserName;
            }
            catch { return "UNKNOWN_HWID"; }
        }

        public bool init(bool autoExitOnMaint = true)
        {
            try
            {
                if (SecurityShield.CheckCheatEngineInstalled()) Environment.Exit(0);

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

                    bool isMaint = (root.TryGetProperty("is_maintenance", out var im) && im.GetBoolean()) || msg.ToLower().Contains("maintenance");
                    if (autoExitOnMaint && isMaint)
                    {
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

        public bool login(string username, string password)
        {
            try
            {
                if (SecurityShield.CheckCheatEngineInstalled()) Environment.Exit(0);

                var payload = new { app_name = this.name, app_token = this.token, username = username.Trim(), password = password, hwid = this.hwid, sessionid = this.sessionid };
                var json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var res = client.PostAsync($"{this.url}/api/v1/client/login", content).GetAwaiter().GetResult();
                var resStr = res.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                bool ok = root.TryGetProperty("success", out var s) && s.GetBoolean();
                if (ok)
                {
                    this.user_data.username = username;
                    this.user_data.subscription = root.TryGetProperty("subscription", out var sub) ? sub.GetString() : "default";
                    this.user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() : "Lifetime";
                    this.user_data.hwid = this.hwid;
                    this.response.success = true;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Logged in";
                    return true;
                }
                else
                {
                    this.response.success = false;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Login failed";
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

        public bool license(string key)
        {
            try
            {
                if (SecurityShield.CheckCheatEngineInstalled()) Environment.Exit(0);

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
                    this.user_data.username = root.TryGetProperty("username", out var u) ? u.GetString() : key;
                    this.user_data.subscription = root.TryGetProperty("subscription", out var sub) ? sub.GetString() : "VIP Tier";
                    this.user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() : "Lifetime";
                    this.user_data.hwid = this.hwid;
                    this.response.success = true;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "License Active";
                    return true;
                }
                else
                {
                    this.response.success = false;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Invalid License";
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

        public bool register(string username, string password, string licenseKey)
        {
            try
            {
                if (SecurityShield.CheckCheatEngineInstalled()) Environment.Exit(0);

                var payload = new { app_name = this.name, app_token = this.token, username = username.Trim(), password = password, license_key = licenseKey.Trim(), hwid = this.hwid, sessionid = this.sessionid };
                var json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                var res = client.PostAsync($"{this.url}/api/v1/client/register", content).GetAwaiter().GetResult();
                var resStr = res.Content.ReadAsStringAsync().GetAwaiter().GetResult();
                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                bool ok = root.TryGetProperty("success", out var s) && s.GetBoolean();
                if (ok)
                {
                    this.user_data.username = username;
                    this.response.success = true;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Registered successfully";
                    return true;
                }
                else
                {
                    this.response.success = false;
                    this.response.message = root.TryGetProperty("message", out var msg) ? msg.GetString() : "Registration failed";
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
            Task.Run(async () =>
            {
                while (true)
                {
                    await Task.Delay(25000);
                    if (string.IsNullOrEmpty(this.sessionid)) continue;
                    if (SecurityShield.CheckCheatEngineInstalled()) Environment.Exit(0);

                    try
                    {
                        var payload = new { app_name = this.name, app_token = this.token, sessionid = this.sessionid, hwid = this.hwid };
                        var json = JsonSerializer.Serialize(payload);
                        var content = new StringContent(json, Encoding.UTF8, "application/json");
                        var res = await client.PostAsync($"{this.url}/api/v1/client/check", content);
                        var resStr = await res.Content.ReadAsStringAsync();
                        using var doc = JsonDocument.Parse(resStr);
                        var root = doc.RootElement;

                        if (root.TryGetProperty("is_maintenance", out var im) && im.GetBoolean())
                        {
                            Environment.Exit(0);
                        }

                        if (root.TryGetProperty("success", out var ok) && !ok.GetBoolean())
                        {
                            Environment.Exit(0);
                        }
                    }
                    catch { }
                }
            });
        }
    }
}
