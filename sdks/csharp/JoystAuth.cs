using System;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Collections.Generic;
using System.Threading;

namespace JoystAuth
{
    public class UserData
    {
        [JsonPropertyName("username")]
        public string username { get; set; } = "";

        [JsonPropertyName("subscription")]
        public string subscription { get; set; } = "";

        [JsonPropertyName("expiry")]
        public string expiry { get; set; } = "";

        [JsonPropertyName("timeleft")]
        public string timeleft { get; set; } = "";

        [JsonPropertyName("hwid")]
        public string hwid { get; set; } = "";

        [JsonPropertyName("ip")]
        public string ip { get; set; } = "";
    }

    public class ResponseData
    {
        [JsonPropertyName("success")]
        public bool success { get; set; }

        [JsonPropertyName("message")]
        public string message { get; set; } = "";
    }

    // ==================== INBUILT ZERO-CONFIG ANTI-CRACK ENGINE ====================
    public static class SecurityShield
    {
        [DllImport("kernel32.dll", SetLastError = true, ExactSpelling = true)]
        private static extern bool IsDebuggerPresent();

        [DllImport("kernel32.dll", SetLastError = true, ExactSpelling = true)]
        private static extern bool CheckRemoteDebuggerPresent(IntPtr hProcess, ref bool isDebuggerPresent);

        private static readonly HashSet<string> BlacklistProcesses = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "httpdebuggerui", "httpdebuggersvc", "fiddler", "wireshark",
            "charles", "x64dbg", "x32dbg", "ida", "ida64", "cheatengine",
            "processhacker", "dnspy", "de4dot", "megadumper", "scylla",
            "die", "detectiteasy", "ghidra", "ollydbg"
        };

        public static bool CheckDebugger()
        {
            if (Debugger.IsAttached) return true;
            if (IsDebuggerPresent()) return true;

            bool isRemote = false;
            CheckRemoteDebuggerPresent(Process.GetCurrentProcess().Handle, ref isRemote);
            return isRemote;
        }

        public static bool ScanAndKillBlacklist()
        {
            bool found = false;
            try
            {
                foreach (var proc in Process.GetProcesses())
                {
                    try
                    {
                        if (BlacklistProcesses.Contains(proc.ProcessName))
                        {
                            found = true;
                            proc.Kill();
                        }
                    }
                    catch { }
                }
            }
            catch { }
            return found;
        }

        public static bool CheckVirtualMachine()
        {
            try
            {
                string compModel = Environment.GetEnvironmentVariable("COMPUTERNAME") ?? "";
                if (compModel.IndexOf("sandbox", StringComparison.OrdinalIgnoreCase) >= 0 ||
                    compModel.IndexOf("vbox", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return true;
                }
            }
            catch { }
            return false;
        }

        public static void StartWatchdog()
        {
            new Thread(() =>
            {
                while (true)
                {
                    if (CheckDebugger() || ScanAndKillBlacklist())
                    {
                        Environment.Exit(0);
                    }
                    Thread.Sleep(2000);
                }
            })
            { IsBackground = true }.Start();
        }
    }

    public class api
    {
        public string name { get; }
        public string token { get; }
        public string version { get; }
        public string url { get; }

        public string hwid { get; private set; }
        public string? sessionid { get; private set; }
        public bool is_initialized { get; private set; }

        public UserData user_data { get; private set; } = new UserData();
        public ResponseData response { get; private set; } = new ResponseData();
        private readonly HttpClient _http;

        public api(string name, string token, string version = "1.0", string url = "https://joystauth.cc")
        {
            this.name = name;
            this.token = token;
            this.version = version;
            this.url = url.TrimEnd('/');
            this.hwid = GetHwid();

            // 🛡️ Automatic Zero-Config Anti-Crack Shield Launch
            if (SecurityShield.CheckDebugger() || SecurityShield.ScanAndKillBlacklist() || SecurityShield.CheckVirtualMachine())
            {
                Environment.Exit(0);
            }
            SecurityShield.StartWatchdog();

            var handler = new HttpClientHandler
            {
                ServerCertificateCustomValidationCallback = (message, cert, chain, errors) => true
            };
            _http = new HttpClient(handler) { Timeout = TimeSpan.FromSeconds(15) };
            _http.DefaultRequestHeaders.Add("User-Agent", "JoystEnclave-CSharp/2.0");
        }

        private string GetHwid()
        {
            try
            {
                string raw = Environment.MachineName + Environment.UserName + Environment.ProcessorCount;
                using var sha = SHA256.Create();
                byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(raw));
                return Convert.ToHexString(hash).ToLower();
            }
            catch
            {
                return "hwid_fallback_" + Guid.NewGuid().ToString("N");
            }
        }

        private async Task<string> HttpPostAsync(string endpoint, object payload)
        {
            try
            {
                string json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");
                var res = await _http.PostAsync($"{url}{endpoint}", content);
                return await res.Content.ReadAsStringAsync();
            }
            catch (Exception ex)
            {
                return $"{{\"success\":false,\"detail\":\"Network error: {ex.Message}\"}}";
            }
        }

        public async Task<bool> InitAsync()
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);

            var payload = new { app_name = name, app_token = token, hwid = hwid };
            string raw = await HttpPostAsync("/api/v1/client/init", payload);

            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    sessionid = root.GetProperty("sessionid").GetString();
                    is_initialized = true;
                    response.success = true;
                    response.message = root.TryGetProperty("message", out var m) ? m.GetString() ?? "" : "Session Initialized";
                    return true;
                }
                else
                {
                    response.success = false;
                    response.message = root.TryGetProperty("detail", out var d) ? d.GetString() ?? "" : "Init failed";
                    return false;
                }
            }
            catch
            {
                response.success = false;
                response.message = "Invalid server response";
                return false;
            }
        }

        public void init() => InitAsync().GetAwaiter().GetResult();

        public async Task<bool> LoginAsync(string username, string password)
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);
            if (!is_initialized) { await InitAsync(); if (!is_initialized) return false; }

            var payload = new
            {
                app_name = name,
                app_token = token,
                username = username,
                password = password,
                hwid = hwid,
                sessionid = sessionid
            };

            string raw = await HttpPostAsync("/api/v1/client/login", payload);
            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    user_data.username = root.GetProperty("username").GetString() ?? username;
                    user_data.subscription = root.GetProperty("subscription").GetString() ?? "default";
                    user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() ?? "" : "";
                    user_data.ip = root.TryGetProperty("ip", out var ip) ? ip.GetString() ?? "" : "";
                    user_data.hwid = hwid;
                    response.success = true;
                    response.message = "Authentication Successful";
                    return true;
                }
                else
                {
                    response.success = false;
                    response.message = root.TryGetProperty("detail", out var d) ? d.GetString() ?? "" : "Login failed";
                    return false;
                }
            }
            catch
            {
                response.success = false;
                response.message = "Invalid login response";
                return false;
            }
        }

        public bool login(string username, string password) => LoginAsync(username, password).GetAwaiter().GetResult();

        
        public async Task<bool> RegisterAsync(string username, string password, string key)
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);
            if (!is_initialized) { await InitAsync(); if (!is_initialized) return false; }

            var payload = new
            {
                app_name = name,
                app_token = token,
                username = username,
                password = password,
                license_key = key,
                hwid = hwid,
                sessionid = sessionid
            };

            string raw = await HttpPostAsync("/api/v1/client/register", payload);
            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    user_data.username = root.TryGetProperty("username", out var u) ? u.GetString() ?? username : username;
                    user_data.subscription = root.TryGetProperty("subscription", out var sub) ? sub.GetString() ?? "default" : "default";
                    user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() ?? "" : "";
                    user_data.ip = root.TryGetProperty("ip", out var ip) ? ip.GetString() ?? "" : "";
                    user_data.hwid = hwid;
                    response.success = true;
                    response.message = root.TryGetProperty("message", out var m) ? m.GetString() ?? "Registration Successful" : "Registration Successful";
                    return true;
                }
                else
                {
                    response.success = false;
                    response.message = root.TryGetProperty("detail", out var d) ? d.GetString() ?? "" : (root.TryGetProperty("message", out var m2) ? m2.GetString() ?? "Registration failed" : "Registration failed");
                    return false;
                }
            }
            catch
            {
                response.success = false;
                response.message = "Invalid registration response";
                return false;
            }
        }

        public bool register(string username, string password, string key) => RegisterAsync(username, password, key).GetAwaiter().GetResult();

        public async Task<bool> UpgradeAsync(string username, string key)
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);
            if (!is_initialized) { await InitAsync(); if (!is_initialized) return false; }

            var payload = new
            {
                app_name = name,
                app_token = token,
                username = username,
                license_key = key,
                sessionid = sessionid
            };

            string raw = await HttpPostAsync("/api/v1/client/upgrade", payload);
            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    user_data.subscription = root.TryGetProperty("subscription", out var sub) ? sub.GetString() ?? "default" : "default";
                    user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() ?? "" : "";
                    response.success = true;
                    response.message = root.TryGetProperty("message", out var m) ? m.GetString() ?? "Upgraded successfully" : "Upgraded successfully";
                    return true;
                }
                else
                {
                    response.success = false;
                    response.message = root.TryGetProperty("detail", out var d) ? d.GetString() ?? "" : (root.TryGetProperty("message", out var m2) ? m2.GetString() ?? "Upgrade failed" : "Upgrade failed");
                    return false;
                }
            }
            catch
            {
                response.success = false;
                response.message = "Invalid upgrade response";
                return false;
            }
        }

        public bool upgrade(string username, string key) => UpgradeAsync(username, key).GetAwaiter().GetResult();

        public async Task<bool> LicenseAsync(string key)
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);
            if (!is_initialized) { await InitAsync(); if (!is_initialized) return false; }

            var payload = new
            {
                app_name = name,
                app_token = token,
                license_key = key,
                hwid = hwid,
                sessionid = sessionid
            };

            string raw = await HttpPostAsync("/api/v1/client/license", payload);
            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    user_data.username = root.GetProperty("username").GetString() ?? key;
                    user_data.subscription = root.GetProperty("subscription").GetString() ?? "default";
                    user_data.expiry = root.TryGetProperty("expires_at", out var exp) ? exp.GetString() ?? "" : "";
                    user_data.ip = root.TryGetProperty("ip", out var ip) ? ip.GetString() ?? "" : "";
                    user_data.hwid = hwid;
                    response.success = true;
                    response.message = "License Verified";
                    return true;
                }
                else
                {
                    response.success = false;
                    response.message = root.TryGetProperty("detail", out var d) ? d.GetString() ?? "" : "License failed";
                    return false;
                }
            }
            catch
            {
                response.success = false;
                response.message = "Invalid license response";
                return false;
            }
        }

        public bool license(string key) => LicenseAsync(key).GetAwaiter().GetResult();

        public async Task<string> VarAsync(string varName)
        {
            if (SecurityShield.CheckDebugger()) Environment.Exit(0);
            if (!is_initialized) return "";

            var payload = new
            {
                app_name = name,
                app_token = token,
                var_name = varName,
                sessionid = sessionid
            };

            string raw = await HttpPostAsync("/api/v1/client/var", payload);
            try
            {
                using var doc = JsonDocument.Parse(raw);
                var root = doc.RootElement;
                if (root.TryGetProperty("success", out var s) && s.GetBoolean())
                {
                    return root.GetProperty("value").GetString() ?? "";
                }
            }
            catch { }
            return "";
        }

        public string var(string varName) => VarAsync(varName).GetAwaiter().GetResult();
    }
}
