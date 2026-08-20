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
        public string ownerid { get; }
        public string secret { get; }
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

        public api(string name, string ownerid, string secret, string version = "1.0", string url = "http://127.0.0.1:8000")
        {
            this.name = name;
            this.ownerid = ownerid;
            this.secret = secret;
            this.version = version;
            this.url = url.TrimEnd('/');
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
                    ownerid = this.ownerid,
                    secret = this.secret,
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
                    enckey = Decrypt(rawEncKey, secret);
                    is_initialized = true;
                    response = new ResponseData { success = true, message = "Initialized successfully" };
                    return true;
                }
                else
                {
                    response = new ResponseData { success = false, message = root.GetProperty("message").GetString() ?? "Init failed" };
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
                                Console.ForegroundColor = ConsoleColor.Red;
                                Console.WriteLine($"\n\n[🚨 LIVE KILL-SWITCH TRIGGERED] {response.message}");
                                Console.WriteLine("Application will terminate in 3 seconds...");
                                Console.ResetColor();
                                Thread.Sleep(3000);
                                Environment.Exit(0);
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
    }
}
