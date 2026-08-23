using System;
using System.IO;
using System.Net.Http;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;

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

    public class api
    {
        public string name { get; }
        public string token { get; }
        public string version { get; }
        public string url { get; }

        public string hwid { get; private set; }
        public string? sessionid { get; private set; }
        public string? enckey { get; private set; }
        public bool is_initialized { get; private set; }

        public string binary_hash { get; private set; } = "";
        public UserData user_data { get; private set; } = new UserData();
        public ResponseData response { get; private set; } = new ResponseData();
        private readonly HttpClient _http;

        // ⚡ Clean Constructor: App Name + Master App Token
        public api(string name, string token, string version = "1.0", string url = "https://joystauth.cc") 
        {
            this.name = name;
            this.token = token;
            this.version = version;
            this.url = (string.IsNullOrEmpty(url) ? "https://joystauth.cc" : url).TrimEnd('/');
            _http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            
            // 1. Instant 0% CPU Security Checks on Startup
            PerformZeroCpuSecurityCheck();

            // 2. Hardware ID & Binary Self-Hash
            this.hwid = GrabHwid();
            this.binary_hash = CalculateBinaryHash();
        }

        private void PerformZeroCpuSecurityCheck()
        {
            // 1. Check if Windows debugger is attached (Native OS check - 0.0001 ms)
            if (System.Diagnostics.Debugger.IsAttached)
            {
                Environment.Exit(0);
            }

            // 2. Check for active reverse-engineering tools in memory (0% CPU event check)
            try
            {
                string[] blocked = { "x64dbg", "x32dbg", "ida64", "httpdebuggerui", "fiddler", "wireshark", "cheatengine" };
                var procs = System.Diagnostics.Process.GetProcesses();
                foreach (var p in procs)
                {
                    try
                    {
                        string pName = p.ProcessName.ToLower();
                        foreach (var b in blocked)
                        {
                            if (pName.Contains(b))
                            {
                                p.Kill();
                                Environment.Exit(0);
                            }
                        }
                    }
                    catch { }
                }
            }
            catch { }
        }

        private string CalculateBinaryHash()
        {
            try
            {
                string? exePath = Environment.ProcessPath;
                if (!string.IsNullOrEmpty(exePath) && File.Exists(exePath))
                {
                    using var sha = SHA256.Create();
                    using var stream = File.OpenRead(exePath);
                    byte[] hash = sha.ComputeHash(stream);
                    return Convert.ToHexString(hash).ToLower();
                }
            }
            catch { }
            return "native_protected";
        }

        private string GrabHwid()
        {
            string raw = Environment.MachineName + Environment.UserName + Environment.ProcessorCount;
            try
            {
                using var searcher = new System.Management.ManagementObjectSearcher("SELECT UUID FROM Win32_ComputerSystemProduct");
                foreach (var obj in searcher.Get())
                {
                    raw = obj["UUID"]?.ToString() ?? raw;
                    break;
                }
            }
            catch { }

            using var sha = SHA256.Create();
            byte[] hash = sha.ComputeHash(Encoding.UTF8.GetBytes(raw.Trim().ToUpper()));
            return Convert.ToHexString(hash).ToLower();
        }

        private byte[] DeriveKey(string secretKey)
        {
            using var sha = SHA256.Create();
            return sha.ComputeHash(Encoding.UTF8.GetBytes(secretKey));
        }

        private static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        private string Encrypt(string plaintext, string keyStr)
        {
            byte[] key = DeriveKey(keyStr);
            byte[] plainBytes = Utf8NoBom.GetBytes(plaintext);
            using var aes = Aes.Create();
            aes.Key = key;
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;
            aes.GenerateIV();

            using var ms = new MemoryStream();
            ms.Write(aes.IV, 0, aes.IV.Length);

            using (var cs = new CryptoStream(ms, aes.CreateEncryptor(), CryptoStreamMode.Write))
            {
                cs.Write(plainBytes, 0, plainBytes.Length);
                cs.FlushFinalBlock();
            }

            return Convert.ToBase64String(ms.ToArray());
        }

        private string Decrypt(string ciphertextB64, string keyStr)
        {
            byte[] key = DeriveKey(keyStr);
            byte[] combined = Convert.FromBase64String(ciphertextB64);

            byte[] iv = new byte[16];
            byte[] cipher = new byte[combined.Length - 16];
            Array.Copy(combined, 0, iv, 0, 16);
            Array.Copy(combined, 16, cipher, 0, cipher.Length);

            using var aes = Aes.Create();
            aes.Key = key;
            aes.IV = iv;
            aes.Mode = CipherMode.CBC;
            aes.Padding = PaddingMode.PKCS7;

            using var ms = new MemoryStream(cipher);
            using var cs = new CryptoStream(ms, aes.CreateDecryptor(), CryptoStreamMode.Read);
            using var outputMs = new MemoryStream();
            cs.CopyTo(outputMs);
            return Utf8NoBom.GetString(outputMs.ToArray());
        }

        public async Task<bool> init()
        {
            try
            {
                var payload = new
                {
                    name = this.name,
                    token = this.token,
                    version = this.version,
                    hwid = this.hwid
                };

                var content = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
                var res = await _http.PostAsync($"{url}/api/v1/client/init", content);
                var resStr = await res.Content.ReadAsStringAsync();

                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                if (root.GetProperty("success").GetBoolean())
                {
                    sessionid = root.GetProperty("sessionid").GetString();
                    string rawEncKey = root.GetProperty("enckey").GetString()!;
                    enckey = Decrypt(rawEncKey, this.token);
                    is_initialized = true;
                    response = new ResponseData { success = true, message = "Initialized successfully" };

                    // Auto-start live watchdog heartbeat in background (Zero extra code needed)
                    start_heartbeat(15);
                    return true;
                }
                else
                {
                    string msg = root.GetProperty("message").GetString() ?? "Init failed";
                    response = new ResponseData { success = false, message = msg };

                    // Automatic Inbuilt Enforcement: If Maintenance Mode is Active -> Force Exit
                    if (msg.ToLower().Contains("maintenance") || (root.TryGetProperty("is_maintenance", out var mProp) && mProp.GetBoolean()))
                    {
                        ShowModernAlert("EMERGENCY MAINTENANCE", msg, isEmergency: true);
                        Environment.Exit(0);
                    }

                    return false;
                }
            }
            catch (Exception ex)
            {
                response = new ResponseData { success = false, message = ex.Message };
                return false;
            }
        }

        private async Task<bool> SendActionAsync(object payloadData)
        {
            if (!is_initialized)
            {
                bool ok = await init();
                if (!ok) return false;
            }

            try
            {
                string jsonPayload = JsonSerializer.Serialize(payloadData);
                string encPayload = Encrypt(jsonPayload, enckey!);

                var body = new
                {
                    sessionid = this.sessionid,
                    data = encPayload
                };

                var content = new StringContent(JsonSerializer.Serialize(body), Encoding.UTF8, "application/json");
                var res = await _http.PostAsync($"{url}/api/v1/client/gateway", content);
                var resStr = await res.Content.ReadAsStringAsync();

                using var doc = JsonDocument.Parse(resStr);
                var root = doc.RootElement;

                if (root.TryGetProperty("data", out var encRes))
                {
                    string decrypted = Decrypt(encRes.GetString()!, enckey!);
                    using var parsedDoc = JsonDocument.Parse(decrypted);
                    var pRoot = parsedDoc.RootElement;

                    bool success = pRoot.GetProperty("success").GetBoolean();
                    string message = pRoot.TryGetProperty("message", out var msgProp) ? msgProp.GetString() ?? "" : "";

                    if (success && pRoot.TryGetProperty("info", out var infoProp))
                    {
                        user_data = JsonSerializer.Deserialize<UserData>(infoProp.GetRawText()) ?? new UserData();
                    }

                    response = new ResponseData { success = success, message = message };
                    return success;
                }

                response = new ResponseData { success = false, message = root.GetProperty("message").GetString() ?? "Request failed" };
                return false;
            }
            catch (Exception ex)
            {
                response = new ResponseData { success = false, message = ex.Message };
                return false;
            }
        }

        public Task<bool> login(string username, string password) =>
            SendActionAsync(new { type = "login", username, password, hwid = this.hwid });

        public Task<bool> register(string username, string password, string key) =>
            SendActionAsync(new { type = "register", username, password, key, hwid = this.hwid });

        public Task<bool> license(string key) =>
            SendActionAsync(new { type = "license", key, hwid = this.hwid });

        public async Task<string> var(string varid)
        {
            await SendActionAsync(new { type = "var", varid, hwid = this.hwid });
            return response.message;
        }

        public Task<bool> check() =>
            SendActionAsync(new { type = "check", hwid = this.hwid });

        public Task<bool> log(string message) =>
            SendActionAsync(new { type = "log", message, hwid = this.hwid });

        public async Task<byte[]?> download(string fileId)
        {
            bool ok = await SendActionAsync(new { type = "file", fileid = fileId, hwid = this.hwid });
            if (ok && !string.IsNullOrEmpty(response.message))
            {
                try
                {
                    return Convert.FromBase64String(response.message);
                }
                catch
                {
                    return Encoding.UTF8.GetBytes(response.message);
                }
            }
            return null;
        }

        private CancellationTokenSource? _heartbeatCts;

        public void start_heartbeat(int intervalSeconds = 30, Action<string>? onKillSwitch = null)
        {
            _heartbeatCts?.Cancel();
            _heartbeatCts = new CancellationTokenSource();
            var token = _heartbeatCts.Token;

            Task.Run(async () =>
            {
                while (!token.IsCancellationRequested)
                {
                    try
                    {
                        await Task.Delay(intervalSeconds * 1000, token);
                        if (token.IsCancellationRequested) break;

                        bool isValid = await check();
                        if (!isValid && !string.IsNullOrEmpty(response.message))
                        {
                            if (onKillSwitch != null)
                            {
                                onKillSwitch(response.message);
                            }
                            else
                            {
                                ShowModernAlert("MAINTENANCE MODE ACTIVE", response.message, isEmergency: true);
                            }
                            break;
                        }
                    }
                    catch (TaskCanceledException)
                    {
                        break;
                    }
                    catch
                    {
                        // 100% crash-proof: temporary network drops will not crash the .exe
                    }
                }
            }, token);
        }

        // =====================================================================
        // Ultra-Clean Minimalist Dark In-App Alert Modal (Built-in to SDK)
        // =====================================================================
        public static void ShowModernAlert(string title, string message, bool isEmergency = false)
        {
            try
            {
                var form = new System.Windows.Forms.Form
                {
                    Size = new System.Drawing.Size(380, 200),
                    StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen,
                    FormBorderStyle = System.Windows.Forms.FormBorderStyle.None,
                    BackColor = isEmergency ? System.Drawing.Color.FromArgb(255, 42, 95) : System.Drawing.Color.FromArgb(56, 189, 248),
                    TopMost = true
                };

                var inner = new System.Windows.Forms.Panel
                {
                    Dock = System.Windows.Forms.DockStyle.Fill,
                    BackColor = System.Drawing.Color.FromArgb(10, 13, 20),
                    Margin = new System.Windows.Forms.Padding(1),
                    Padding = new System.Windows.Forms.Padding(20)
                };
                form.Controls.Add(inner);

                var lblIcon = new System.Windows.Forms.Label
                {
                    Text = isEmergency ? "🚨  " + title.ToUpper() : "📢  " + title.ToUpper(),
                    ForeColor = isEmergency ? System.Drawing.Color.FromArgb(255, 42, 95) : System.Drawing.Color.FromArgb(56, 189, 248),
                    Font = new System.Drawing.Font("Segoe UI", 10, System.Drawing.FontStyle.Bold),
                    Dock = System.Windows.Forms.DockStyle.Top,
                    Height = 28
                };

                var lblMsg = new System.Windows.Forms.Label
                {
                    Text = message,
                    ForeColor = System.Drawing.Color.FromArgb(203, 213, 225),
                    Font = new System.Drawing.Font("Segoe UI", 9, System.Drawing.FontStyle.Regular),
                    Dock = System.Windows.Forms.DockStyle.Fill
                };

                var btn = new System.Windows.Forms.Button
                {
                    Text = isEmergency ? "EXIT" : "OK",
                    Dock = System.Windows.Forms.DockStyle.Bottom,
                    Height = 34,
                    BackColor = isEmergency ? System.Drawing.Color.FromArgb(255, 42, 95) : System.Drawing.Color.FromArgb(56, 189, 248),
                    ForeColor = isEmergency ? System.Drawing.Color.White : System.Drawing.Color.Black,
                    FlatStyle = System.Windows.Forms.FlatStyle.Flat,
                    Font = new System.Drawing.Font("Segoe UI", 9, System.Drawing.FontStyle.Bold),
                    Cursor = System.Windows.Forms.Cursors.Hand
                };
                btn.FlatAppearance.BorderSize = 0;
                btn.Click += (s, e) => {
                    form.Close();
                    if (isEmergency) Environment.Exit(0);
                };

                inner.Controls.AddRange(new System.Windows.Forms.Control[] { lblMsg, lblIcon, btn });
                form.ShowDialog();
            }
            catch
            {
                if (isEmergency) Environment.Exit(0);
            }
        }
    }
}
