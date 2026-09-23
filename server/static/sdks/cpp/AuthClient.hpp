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
#include <sddl.h>

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

    // ==================== JOYST SECURITY ENCLAVE & ANTI-TAMPER ====================
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

        static bool CheckCheatEngineInstalled(bool triggerAlert = false) {
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
            return false;
        }

        static bool CheckDebugger(bool triggerAlert = false) {
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

            return false;
        }

        static bool ScanAndKillBlacklist(bool triggerAlert = false) {
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

        // Safe for Emulators (BlueStacks/LDPlayer/MSI/MEmu) & DLL Injection
        static bool CheckVirtualMachine(bool triggerAlert = false) {
            return false;
        }

        static void StartWatchdog() {
            // Disabled in client SDK to avoid unexpected game / emulator crashes
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
        std::string last_shown_notification = "";

        std::string GetHwid() {
            HW_PROFILE_INFO hwProfileInfo;
            if (GetCurrentHwProfileA(&hwProfileInfo)) {
                return std::string(hwProfileInfo.szHwProfileGuid);
            }

            DWORD serialNumber = 0;
            if (GetVolumeInformationA("C:\\", NULL, 0, &serialNumber, NULL, NULL, NULL, 0)) {
                return std::to_string(serialNumber);
            }

            return "HWID-DEFAULT-JOYST";
        }

        std::string HttpPost(const std::string& endpoint, const std::string& json_payload) {
            std::string full_url = url + endpoint;
            std::string response_data = "";

            URL_COMPONENTSA urlComp;
            memset(&urlComp, 0, sizeof(urlComp));
            urlComp.dwStructSize = sizeof(urlComp);
            urlComp.dwHostNameLength = 1;
            urlComp.dwUrlPathLength = 1;
            urlComp.dwExtraInfoLength = 1;

            char hostName[256] = { 0 };
            char urlPath[1024] = { 0 };
            urlComp.lpszHostName = hostName;
            urlComp.dwHostNameLength = sizeof(hostName);
            urlComp.lpszUrlPath = urlPath;
            urlComp.dwUrlPathLength = sizeof(urlPath);

            if (!InternetCrackUrlA(full_url.c_str(), (DWORD)full_url.length(), 0, &urlComp)) {
                return "{\"success\":false,\"message\":\"Invalid URL format (" + full_url + ")\"}";
            }

            HINTERNET hInternet = InternetOpenA("JoystAuth-Native-Client/1.0", INTERNET_OPEN_TYPE_PRECONFIG, NULL, NULL, 0);
            if (!hInternet) {
                return "{\"success\":false,\"message\":\"Failed to initialize Windows Internet subsystem.\"}";
            }

            INTERNET_PORT port = urlComp.nPort;
            if (port == 0) {
                port = (urlComp.nScheme == INTERNET_SCHEME_HTTPS) ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
            }

            HINTERNET hConnect = InternetConnectA(hInternet, urlComp.lpszHostName, port, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
            if (!hConnect) {
                InternetCloseHandle(hInternet);
                return "{\"success\":false,\"message\":\"Failed to connect to authentication server.\"}";
            }

            DWORD flags = INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE | INTERNET_FLAG_PRAGMA_NOCACHE;
            if (urlComp.nScheme == INTERNET_SCHEME_HTTPS) {
                flags |= INTERNET_FLAG_SECURE | INTERNET_FLAG_IGNORE_CERT_CN_INVALID | INTERNET_FLAG_IGNORE_CERT_DATE_INVALID;
            }

            std::string pathAndExtra = std::string(urlComp.lpszUrlPath);
            if (urlComp.dwExtraInfoLength > 0 && urlComp.lpszExtraInfo) {
                pathAndExtra += std::string(urlComp.lpszExtraInfo);
            }

            HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", pathAndExtra.c_str(), NULL, NULL, NULL, flags, 0);
            if (!hRequest) {
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{\"success\":false,\"message\":\"Failed to create HTTP request.\"}";
            }

            DWORD timeout = 12000;
            InternetSetOptionA(hRequest, INTERNET_OPTION_CONNECT_TIMEOUT, &timeout, sizeof(timeout));
            InternetSetOptionA(hRequest, INTERNET_OPTION_RECEIVE_TIMEOUT, &timeout, sizeof(timeout));
            InternetSetOptionA(hRequest, INTERNET_OPTION_SEND_TIMEOUT, &timeout, sizeof(timeout));

            std::string headers = "Content-Type: application/json\r\nAccept: application/json\r\nUser-Agent: JoystAuth-Native-Client/1.0\r\n";

            BOOL bSend = HttpSendRequestA(hRequest, headers.c_str(), (DWORD)headers.length(), (LPVOID)json_payload.c_str(), (DWORD)json_payload.length());
            if (!bSend) {
                InternetCloseHandle(hRequest);
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{\"success\":false,\"message\":\"Network connection timed out or unreachable (" + url + ").\"}";
            }

            char buffer[4096];
            DWORD bytesRead = 0;
            while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
                buffer[bytesRead] = '\0';
                response_data += buffer;
            }

            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);

            if (response_data.empty()) {
                return "{\"success\":false,\"message\":\"Empty response from JoystAuth server.\"}";
            }

            return response_data;
        }

        std::string ExtractJsonValue(const std::string& json, const std::string& key) {
            std::string searchKey = "\"" + key + "\":";
            size_t pos = json.find(searchKey);
            if (pos == std::string::npos) return "";

            pos += searchKey.length();
            while (pos < json.length() && (json[pos] == ' ' || json[pos] == '\t')) pos++;

            if (pos < json.length() && json[pos] == '"') {
                pos++;
                size_t end = json.find('"', pos);
                if (end != std::string::npos) {
                    return json.substr(pos, end - pos);
                }
            } else {
                size_t end = json.find_first_of(",}\n\r", pos);
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

    public:
        user_data_class user_data;
        response_class response;

        api(std::string name, std::string token, std::string version = "1.0", std::string url = "https://joystauth.cc", std::string path = "") {
            this->name = name;
            this->token = token;
            this->version = version;
            this->url = url;
            this->hwid = GetHwid();
            this->is_initialized = false;
        }

        void init(bool auto_handle_maintenance_and_popup = false) {
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
                }
            }
        }

        bool login(std::string username, std::string password, std::string code = "") {
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
