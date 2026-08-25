#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <set>
#include <windows.h>
#include <wininet.h>
#include <wincrypt.h>
#include <tlhelp32.h>
#include <thread>
#include <chrono>

#pragma comment(lib, "wininet.lib")
#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "advapi32.lib")
#pragma comment(lib, "user32.lib")

namespace JoystAuth {

    struct user_data_class {
        std::string username;
        std::string subscription;
        std::string expiry;
        std::string timeleft;
        std::string hwid;
        std::string ip;
    };

    struct response_class {
        bool success = false;
        std::string message;
        bool is_maintenance = false;
        std::string active_notification;
    };

    // ==================== INBUILT MILITARY-GRADE ANTI-TAMPER & SECURITY SHIELD ====================
    class SecurityShield {
    private:
        static inline std::vector<std::string> blacklist_processes = {
            "httpdebuggerui.exe", "httpdebuggersvc.exe", "fiddler.exe",
            "wireshark.exe", "charles.exe", "x64dbg.exe", "x32dbg.exe",
            "ida.exe", "ida64.exe", "cheatengine.exe", "cheatengine-x86_64.exe",
            "cheatengine-i386.exe", "cheatengine-x86_64-sse4-avx2.exe", "cheatengine-arm64.exe",
            "processhacker.exe", "dnspy.exe", "de4dot.exe", "megadumper.exe",
            "scylla.exe", "die.exe", "detectiteasy.exe", "ghidra.exe", "ollydbg.exe"
        };

        static std::string to_lower(const std::string& str) {
            std::string res = str;
            for (char& c : res) c = (char)std::tolower(c);
            return res;
        }

    public:
        static void ShowSecurityAlert(const std::string& reason, const std::string& details = "") {
            std::string msg = "⚠️ JOYST SECURITY ENCLAVE ALERT ⚠️\n\n" + reason;
            if (!details.empty()) {
                msg += "\n\nDetails: " + details;
            }
            msg += "\n\nPlease resolve this issue before running the software.";
            MessageBoxA(NULL, msg.c_str(), "JOYST - SECURITY INTEGRITY LOCK", MB_ICONSTOP | MB_TOPMOST | MB_SETFOREGROUND);
        }

        static bool CheckCheatEngineInstalled(bool triggerAlert = true) {
            // 1. Process Scan
            HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (hSnapshot != INVALID_HANDLE_VALUE) {
                PROCESSENTRY32 pe;
                pe.dwSize = sizeof(PROCESSENTRY32);
                if (Process32First(hSnapshot, &pe)) {
                    do {
                        std::string pName = to_lower(pe.szExeFile);
                        if (pName.find("cheatengine") != std::string::npos ||
                            pName.find("cheat engine") != std::string::npos ||
                            pName == "ce.exe") {
                            CloseHandle(hSnapshot);
                            if (triggerAlert) {
                                ShowSecurityAlert("Cheat Engine process is currently running on this PC!", "Running Process: " + std::string(pe.szExeFile));
                            }
                            return true;
                        }
                    } while (Process32Next(hSnapshot, &pe));
                }
                CloseHandle(hSnapshot);
            }

            // 2. Active Window Class / Title Scan
            const char* window_titles[] = {
                "Cheat Engine", "Cheat Engine 7.5", "Cheat Engine 7.4", "Cheat Engine 7.3",
                "Cheat Engine 7.2", "Cheat Engine 7.1", "Cheat Engine 7.0"
            };
            for (const auto& wt : window_titles) {
                HWND ceHwnd = FindWindowA("Window", wt);
                if (!ceHwnd) ceHwnd = FindWindowA(NULL, wt);
                if (!ceHwnd) ceHwnd = FindWindowA(wt, NULL);
                if (ceHwnd) {
                    if (triggerAlert) {
                        ShowSecurityAlert("Active Cheat Engine Window detected!", "Window: " + std::string(wt));
                    }
                    return true;
                }
            }

            // 3. Kernel Driver Device Handles
            const char* driver_devices[] = {
                "\\.\\CEDRIVER75", "\\.\\CEDRIVER74", "\\.\\CEDRIVER73",
                "\\.\\CEDRIVER72", "\\.\\CEDRIVER71", "\\.\\CEDRIVER70",
                "\\.\\DBK64", "\\.\\DBK32"
            };
            for (const auto& dev : driver_devices) {
                HANDLE hDev = CreateFileA(dev, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
                if (hDev != INVALID_HANDLE_VALUE) {
                    CloseHandle(hDev);
                    if (triggerAlert) {
                        ShowSecurityAlert("Kernel Memory Tampering Driver detected!", "Active Driver Handle: " + std::string(dev));
                    }
                    return true;
                }
            }

            // 4. Windows Registry Installation Entries
            HKEY hKey;
            const char* reg_keys[] = {
                "Software\\Cheat Engine",
                "SOFTWARE\\Cheat Engine",
                "SOFTWARE\\WOW6432Node\\Cheat Engine",
                "SYSTEM\\CurrentControlSet\\Services\\CEDRIVER75",
                "SYSTEM\\CurrentControlSet\\Services\\CEDRIVER74",
                "SYSTEM\\CurrentControlSet\\Services\\CEDRIVER73",
                "SYSTEM\\CurrentControlSet\\Services\\DBK64"
            };
            for (const auto& rk : reg_keys) {
                if (RegOpenKeyExA(HKEY_CURRENT_USER, rk, 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
                    RegCloseKey(hKey);
                    if (triggerAlert) {
                        ShowSecurityAlert("Cheat Engine installation registry keys detected!", "Registry Key: HKCU\\" + std::string(rk));
                    }
                    return true;
                }
                if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, rk, 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
                    RegCloseKey(hKey);
                    if (triggerAlert) {
                        ShowSecurityAlert("Cheat Engine installation registry keys detected!", "Registry Key: HKLM\\" + std::string(rk));
                    }
                    return true;
                }
            }

            // 5. Filesystem Install Directories
            std::vector<std::string> ce_dirs = {
                "C:\\Program Files\\Cheat Engine 7.5",
                "C:\\Program Files\\Cheat Engine 7.4",
                "C:\\Program Files\\Cheat Engine 7.3",
                "C:\\Program Files\\Cheat Engine 7.2",
                "C:\\Program Files\\Cheat Engine 7.1",
                "C:\\Program Files\\Cheat Engine 7.0",
                "C:\\Program Files\\Cheat Engine",
                "C:\\Program Files (x86)\\Cheat Engine 7.5",
                "C:\\Program Files (x86)\\Cheat Engine 7.4",
                "C:\\Program Files (x86)\\Cheat Engine 7.3",
                "C:\\Program Files (x86)\\Cheat Engine 7.2",
                "C:\\Program Files (x86)\\Cheat Engine"
            };
            
            char* appData = nullptr;
            size_t len = 0;
            if (_dupenv_s(&appData, &len, "APPDATA") == 0 && appData != nullptr) {
                ce_dirs.push_back(std::string(appData) + "\\Cheat Engine");
                free(appData);
            }

            for (const auto& dir : ce_dirs) {
                DWORD attrs = GetFileAttributesA(dir.c_str());
                if (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY)) {
                    if (triggerAlert) {
                        ShowSecurityAlert("Cheat Engine installation folder detected!", "Directory: " + dir);
                    }
                    return true;
                }
            }

            return false;
        }

        static bool CheckDebugger(bool triggerAlert = true) {
            if (IsDebuggerPresent()) {
                if (triggerAlert) ShowSecurityAlert("Active Windows Debugger detected attached to this process!");
                return true;
            }

            BOOL is_remote = FALSE;
            CheckRemoteDebuggerPresent(GetCurrentProcess(), &is_remote);
            if (is_remote) {
                if (triggerAlert) ShowSecurityAlert("Remote Debugger / Kernel Debug Port detected attached to this process!");
                return true;
            }

#if defined(_WIN64)
            unsigned char* ppeb = (unsigned char*)__readgsqword(0x60);
            if (ppeb && ppeb[2]) {
                if (triggerAlert) ShowSecurityAlert("Process Environment Block (PEB) BeingDebugged flag is active!");
                return true;
            }
#elif defined(_WIN32)
            unsigned char* ppeb = (unsigned char*)__readfsdword(0x30);
            if (ppeb && ppeb[2]) {
                if (triggerAlert) ShowSecurityAlert("Process Environment Block (PEB) BeingDebugged flag is active!");
                return true;
            }
#endif

            CONTEXT ctx = { 0 };
            ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
            HANDLE hThread = GetCurrentThread();
            if (GetThreadContext(hThread, &ctx)) {
                if (ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3) {
                    if (triggerAlert) ShowSecurityAlert("Hardware Breakpoints / Debug Registers (DR0-DR3) detected!");
                    return true;
                }
            }

            return false;
        }

        static bool ScanAndKillBlacklist(bool triggerAlert = true) {
            HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (hSnapshot == INVALID_HANDLE_VALUE) return false;

            PROCESSENTRY32 pe;
            pe.dwSize = sizeof(PROCESSENTRY32);

            bool found = false;
            std::string detected_proc = "";

            if (Process32First(hSnapshot, &pe)) {
                do {
                    std::string pName = to_lower(pe.szExeFile);
                    for (const auto& bl : blacklist_processes) {
                        bool is_match = false;
                        if (bl.length() <= 6) {
                            is_match = (pName == bl);
                        } else {
                            is_match = (pName.find(bl) != std::string::npos);
                        }
                        if (is_match) {
                            found = true;
                            detected_proc = pe.szExeFile;
                            HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                            if (hProc) {
                                TerminateProcess(hProc, 0);
                                CloseHandle(hProc);
                            }
                            break;
                        }
                    }
                    if (found) break;
                } while (Process32Next(hSnapshot, &pe));
            }
            CloseHandle(hSnapshot);

            if (found && triggerAlert) {
                ShowSecurityAlert("Prohibited Reverse-Engineering / Tampering Tool detected!", "Detected Process: " + detected_proc);
            }
            return found;
        }

        static bool CheckVirtualMachine(bool triggerAlert = true) {
            HKEY hKey;
            if (RegOpenKeyExA(HKEY_LOCAL_MACHINE, "HARDWARE\\DESCRIPTION\\System", 0, KEY_READ, &hKey) == ERROR_SUCCESS) {
                char buf[256] = { 0 };
                DWORD size = sizeof(buf);
                if (RegQueryValueExA(hKey, "SystemBiosVersion", NULL, NULL, (LPBYTE)buf, &size) == ERROR_SUCCESS) {
                    std::string bios = to_lower(buf);
                    if (bios.find("vbox") != std::string::npos ||
                        bios.find("qemu") != std::string::npos ||
                        bios.find("vmware") != std::string::npos) {
                        RegCloseKey(hKey);
                        if (triggerAlert) {
                            ShowSecurityAlert("Virtual Machine / Hypervisor Environment detected!", "BIOS String: " + bios);
                        }
                        return true;
                    }
                }
                RegCloseKey(hKey);
            }
            return false;
        }

        static void StartWatchdog() {
            std::thread([]() {
                while (true) {
                    if (CheckDebugger(true) || ScanAndKillBlacklist(true) || CheckCheatEngineInstalled(true)) {
                        ExitProcess(0);
                    }
                    std::this_thread::sleep_for(std::chrono::seconds(2));
                }
            }).detach();
        }
    };

    class api {
    private:
        std::string name;
        std::string token;
        std::string version;
        std::string url;
        std::string sessionid;
        std::string hwid;
        bool is_initialized = false;
        static inline std::string last_shown_notification = "";

        std::string GetHwid() {
            HW_PROFILE_INFO hwProfileInfo;
            if (GetCurrentHwProfileA(&hwProfileInfo)) {
                HCRYPTPROV hCryptProv;
                HCRYPTHASH hHash;
                BYTE bHash[32];
                DWORD dwHashLen = 32;
                std::string raw = hwProfileInfo.szHwProfileGuid;

                if (CryptAcquireContext(&hCryptProv, NULL, NULL, PROV_RSA_AES, CRYPT_VERIFYCONTEXT)) {
                    if (CryptCreateHash(hCryptProv, CALG_SHA_256, 0, 0, &hHash)) {
                        CryptHashData(hHash, (BYTE*)raw.c_str(), (DWORD)raw.length(), 0);
                        if (CryptGetHashParam(hHash, HP_HASHVAL, bHash, &dwHashLen, 0)) {
                            char hex[65] = { 0 };
                            for (DWORD i = 0; i < dwHashLen; i++) {
                                sprintf_s(&hex[i * 2], 3, "%02x", bHash[i]);
                            }
                            CryptDestroyHash(hHash);
                            CryptReleaseContext(hCryptProv, 0);
                            return std::string(hex);
                        }
                        CryptDestroyHash(hHash);
                    }
                    CryptReleaseContext(hCryptProv, 0);
                }
                return raw;
            }
            return "DEFAULT_HWID_ENCLAVE";
        }

        std::string HttpPost(const std::string& endpoint, const std::string& data) {
            std::string response = "";
            HINTERNET hInternet = InternetOpenA("JoystEnclave-Client/2.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
            if (!hInternet) {
                return "{\"success\":false,\"message\":\"Failed to open internet connection. Please check your network.\"}";
            }

            std::string domain = url;
            bool isHttps = false;
            if (domain.find("https://") == 0) {
                isHttps = true;
                domain = domain.substr(8);
            } else if (domain.find("http://") == 0) {
                domain = domain.substr(7);
            }

            size_t slashPos = domain.find('/');
            if (slashPos != std::string::npos) {
                domain = domain.substr(0, slashPos);
            }

            INTERNET_PORT port = isHttps ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
            HINTERNET hConnect = InternetConnectA(hInternet, domain.c_str(), port, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
            if (!hConnect) {
                InternetCloseHandle(hInternet);
                return "{\"success\":false,\"message\":\"Failed to connect to authentication server (" + url + "). Server may be offline.\"}";
            }

            DWORD flags = INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE;
            if (isHttps) flags |= INTERNET_FLAG_SECURE | INTERNET_FLAG_IGNORE_CERT_CN_INVALID | INTERNET_FLAG_IGNORE_CERT_DATE_INVALID;

            HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", endpoint.c_str(), NULL, NULL, NULL, flags, 0);
            if (!hRequest) {
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{\"success\":false,\"message\":\"Failed to open HTTP request to " + endpoint + "\"}";
            }

            std::string headers = "Content-Type: application/json\r\n";
            BOOL bSend = HttpSendRequestA(hRequest, headers.c_str(), (DWORD)headers.length(), (LPVOID)data.c_str(), (DWORD)data.length());

            if (bSend) {
                char buffer[4096];
                DWORD bytesRead = 0;
                while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
                    buffer[bytesRead] = '\0';
                    response += buffer;
                }
            } else {
                response = "{\"success\":false,\"message\":\"Failed to send request to authentication server (Error: " + std::to_string(GetLastError()) + ")\"}";
            }

            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            return response;
        }

        std::string ExtractJsonValue(const std::string& json, const std::string& key) {
            std::string pattern = "\"" + key + "\":";
            size_t pos = json.find(pattern);
            if (pos == std::string::npos) return "";

            pos += pattern.length();
            while (pos < json.length() && (json[pos] == ' ' || json[pos] == '\t')) pos++;

            if (pos >= json.length()) return "";

            if (json[pos] == '"') {
                size_t start = pos + 1;
                size_t end = json.find('"', start);
                if (end != std::string::npos) return json.substr(start, end - start);
            } else {
                size_t end = json.find_first_of(",}\r\n", pos);
                if (end != std::string::npos) {
                    std::string val = json.substr(pos, end - pos);
                    while (!val.empty() && (val.back() == ' ' || val.back() == '\t')) val.pop_back();
                    return val;
                }
            }
            return "";
        }

        std::string ExtractFirstNotification(const std::string& json) {
            size_t notifPos = json.find("\"notifications\":");
            if (notifPos == std::string::npos) return "";
            size_t msgPos = json.find("\"message\":", notifPos);
            if (msgPos == std::string::npos) return "";
            return ExtractJsonValue(json.substr(msgPos - 1), "message");
        }

        void StartLiveHeartbeatWatchdog() {
            std::thread([this]() {
                while (true) {
                    std::this_thread::sleep_for(std::chrono::seconds(25));
                    if (!this->is_initialized || this->sessionid.empty()) continue;

                    std::string payload = "{\"app_name\":\"" + this->name + "\",\"app_token\":\"" + this->token + "\",\"sessionid\":\"" + this->sessionid + "\",\"hwid\":\"" + this->hwid + "\"}";
                    std::string res = this->HttpPost("/api/v1/client/check", payload);

                    std::string notif = this->ExtractFirstNotification(res);
                    if (!notif.empty() && notif != last_shown_notification) {
                        last_shown_notification = notif;
                        MessageBoxA(NULL, notif.c_str(), "JOYST NOTIFICATION", MB_ICONINFORMATION | MB_TOPMOST);
                    }

                    if (this->ExtractJsonValue(res, "is_maintenance") == "true" || res.find("\"is_maintenance\":true") != std::string::npos) {
                        std::string msg = this->ExtractJsonValue(res, "message");
                        if (msg.empty()) msg = "Application is currently under maintenance.";
                        MessageBoxA(NULL, msg.c_str(), "JOYST - APPLICATION MAINTENANCE", MB_ICONWARNING | MB_TOPMOST);
                        ExitProcess(0);
                    }

                    if (this->ExtractJsonValue(res, "success") == "false") {
                        std::string msg = this->ExtractJsonValue(res, "message");
                        if (msg.find("banned") != std::string::npos || msg.find("expired") != std::string::npos || msg.find("HWID") != std::string::npos || msg.find("paused") != std::string::npos || msg.find("revoked") != std::string::npos) {
                            MessageBoxA(NULL, msg.c_str(), "JOYST - SECURITY INTEGRITY LOCK", MB_ICONERROR | MB_TOPMOST);
                            ExitProcess(0);
                        }
                    }
                }
            }).detach();
        }

    public:
        user_data_class user_data;
        response_class response;

        api(std::string name, std::string token, std::string version = "1.0", std::string url = "https://joystauth.cc", std::string path = "") {
            this->name = name;
            this->token = token;
            this->version = version;
            this->url = url;
            this->hwid = GetHwid();

            // ⚡ 1. Security scan on startup with explicit messageboxes
            if (SecurityShield::CheckCheatEngineInstalled(true)) {
                ExitProcess(0);
            }
            if (SecurityShield::CheckDebugger(true) || SecurityShield::ScanAndKillBlacklist(true) || SecurityShield::CheckVirtualMachine(true)) {
                ExitProcess(0);
            }
            SecurityShield::StartWatchdog();

            // ⚡ 2. Startup initialization
            this->init(true);

            // ⚡ 3. Launch real-time background watchdog
            this->StartLiveHeartbeatWatchdog();
        }

        void init(bool auto_handle_maintenance_and_popup = true) {
            if (SecurityShield::CheckDebugger(true) || SecurityShield::CheckCheatEngineInstalled(true)) {
                ExitProcess(0);
            }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"version\":\"" + version + "\",\"hwid\":\"" + hwid + "\"}";
            std::string res = HttpPost("/api/v1/client/init", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                this->sessionid = ExtractJsonValue(res, "sessionid");
                this->is_initialized = true;
                this->response.success = true;
                this->response.message = ExtractJsonValue(res, "message");
                this->response.is_maintenance = false;
                this->response.active_notification = ExtractFirstNotification(res);

                if (auto_handle_maintenance_and_popup && !this->response.active_notification.empty()) {
                    last_shown_notification = this->response.active_notification;
                    MessageBoxA(NULL, this->response.active_notification.c_str(), "JOYST NOTIFICATION", MB_ICONINFORMATION | MB_TOPMOST);
                }
            } else {
                this->response.success = false;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = ExtractJsonValue(res, "detail");
                if (msg.empty()) msg = "Failed to connect to authentication server (" + url + "). Please verify your network.";
                this->response.message = msg;
                this->response.is_maintenance = (ExtractJsonValue(res, "is_maintenance") == "true" || res.find("\"is_maintenance\":true") != std::string::npos);

                if (auto_handle_maintenance_and_popup) {
                    std::string title = "JOYST - ACCESS BLOCKED";
                    if (this->response.is_maintenance) {
                        title = "JOYST - APPLICATION MAINTENANCE";
                    } else if (msg.find("Update required") != std::string::npos || msg.find("update") != std::string::npos) {
                        title = "JOYST - UPDATE REQUIRED";
                    }
                    MessageBoxA(NULL, this->response.message.c_str(), title.c_str(), MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND);
                    ExitProcess(0);
                }
            }
        }

        bool login(std::string username, std::string password, std::string code = "") {
            if (SecurityShield::CheckDebugger(true) || SecurityShield::CheckCheatEngineInstalled(true)) {
                ExitProcess(0);
            }
            if (!is_initialized) { init(false); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"version\":\"" + version + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/login", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                if (user_data.expiry.empty()) user_data.expiry = ExtractJsonValue(res, "expiry");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = "Authentication Successful";
                this->response.message = msg;
                return true;
            } else {
                this->response.success = false;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = ExtractJsonValue(res, "detail");
                if (msg.empty()) msg = "Login failed! Please check credentials.";
                this->response.message = msg;
                return false;
            }
        }

        bool license(std::string key) {
            if (SecurityShield::CheckDebugger(true) || SecurityShield::CheckCheatEngineInstalled(true)) {
                ExitProcess(0);
            }
            if (!is_initialized) { init(false); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"version\":\"" + version + "\",\"license_key\":\"" + key + "\",\"key\":\"" + key + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/license", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                if (user_data.expiry.empty()) user_data.expiry = ExtractJsonValue(res, "expiry");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = "License Authenticated Successfully";
                this->response.message = msg;
                return true;
            } else {
                this->response.success = false;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = ExtractJsonValue(res, "detail");
                if (msg.empty()) msg = "License authentication failed! Invalid or expired key.";
                this->response.message = msg;
                return false;
            }
        }

                bool checkblack() {
            return false;
        }

        bool regstr(std::string username, std::string password, std::string key, std::string email = "") {
            return register_user(username, password, key);
        }

        bool register_user(std::string username, std::string password, std::string key) {
            if (SecurityShield::CheckDebugger(true) || SecurityShield::CheckCheatEngineInstalled(true)) {
                ExitProcess(0);
            }
            if (!is_initialized) { init(false); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"version\":\"" + version + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"license_key\":\"" + key + "\",\"key\":\"" + key + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/register", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                this->response.message = ExtractJsonValue(res, "message");
                return true;
            } else {
                this->response.success = false;
                std::string msg = ExtractJsonValue(res, "message");
                if (msg.empty()) msg = ExtractJsonValue(res, "detail");
                this->response.message = msg;
                return false;
            }
        }

        std::string var(std::string var_name) {
            if (!is_initialized) return "";
            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"var_name\":\"" + var_name + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/var", payload);
            if (ExtractJsonValue(res, "success") == "true") {
                return ExtractJsonValue(res, "value");
            }
            return "";
        }
    };
}


namespace KeyAuth {
    using api = JoystAuth::api;
    using user_data_class = JoystAuth::user_data_class;
    using response_class = JoystAuth::response_class;
}
