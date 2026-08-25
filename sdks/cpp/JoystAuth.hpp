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

    // ==================== INBUILT MILITARY-GRADE ANTI-CRACK ENGINE ====================
    class SecurityShield {
    private:
        static inline std::vector<std::string> blacklist_processes = {
            "httpdebuggerui.exe", "httpdebuggersvc.exe", "fiddler.exe",
            "wireshark.exe", "charles.exe", "x64dbg.exe", "x32dbg.exe",
            "ida.exe", "ida64.exe", "cheatengine.exe", "processhacker.exe",
            "dnspy.exe", "de4dot.exe", "megadumper.exe", "scylla.exe",
            "die.exe", "detectiteasy.exe", "ghidra.exe", "ollydbg.exe"
        };

        static std::string to_lower(const std::string& str) {
            std::string res = str;
            for (char& c : res) c = (char)std::tolower(c);
            return res;
        }

    public:
        static bool CheckDebugger() {
            if (IsDebuggerPresent()) return true;

            BOOL is_remote = FALSE;
            CheckRemoteDebuggerPresent(GetCurrentProcess(), &is_remote);
            if (is_remote) return true;

#if defined(_WIN64)
            unsigned char* ppeb = (unsigned char*)__readgsqword(0x60);
            if (ppeb && ppeb[2]) return true;
#elif defined(_WIN32)
            unsigned char* ppeb = (unsigned char*)__readfsdword(0x30);
            if (ppeb && ppeb[2]) return true;
#endif

            CONTEXT ctx = { 0 };
            ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
            HANDLE hThread = GetCurrentThread();
            if (GetThreadContext(hThread, &ctx)) {
                if (ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3) return true;
            }

            return false;
        }

        static bool ScanAndKillBlacklist() {
            HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (hSnapshot == INVALID_HANDLE_VALUE) return false;

            PROCESSENTRY32 pe;
            pe.dwSize = sizeof(PROCESSENTRY32);

            bool found = false;
            if (Process32First(hSnapshot, &pe)) {
                do {
                    std::string pName = to_lower(pe.szExeFile);
                    for (const auto& bl : blacklist_processes) {
                        if (pName.find(bl) != std::string::npos) {
                            found = true;
                            HANDLE hProc = OpenProcess(PROCESS_TERMINATE, FALSE, pe.th32ProcessID);
                            if (hProc) {
                                TerminateProcess(hProc, 0);
                                CloseHandle(hProc);
                            }
                        }
                    }
                } while (Process32Next(hSnapshot, &pe));
            }
            CloseHandle(hSnapshot);
            return found;
        }

        static bool CheckVirtualMachine() {
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
                    if (CheckDebugger() || ScanAndKillBlacklist()) {
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
                return std::string(hwProfileInfo.szHwProfileGuid);
            }
            char compName[MAX_COMPUTERNAME_LENGTH + 1];
            DWORD size = sizeof(compName);
            GetComputerNameA(compName, &size);
            return std::string(compName);
        }

        std::string HttpPost(const std::string& endpoint, const std::string& json_payload) {
            std::string full_url = url + endpoint;
            HINTERNET hInternet = InternetOpenA("JoystEnclave-Cpp/2.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
            if (!hInternet) return "{}";

            URL_COMPONENTSA urlComp;
            memset(&urlComp, 0, sizeof(urlComp));
            urlComp.dwStructSize = sizeof(urlComp);
            char host[256] = {0};
            char path[1024] = {0};
            urlComp.lpszHostName = host;
            urlComp.dwHostNameLength = sizeof(host);
            urlComp.lpszUrlPath = path;
            urlComp.dwUrlPathLength = sizeof(path);

            if (!InternetCrackUrlA(full_url.c_str(), (DWORD)full_url.length(), 0, &urlComp)) {
                InternetCloseHandle(hInternet);
                return "{}";
            }

            INTERNET_PORT port = (urlComp.nScheme == INTERNET_SCHEME_HTTPS) ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT;
            DWORD flags = (urlComp.nScheme == INTERNET_SCHEME_HTTPS) ? (INTERNET_FLAG_SECURE | INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE) : INTERNET_FLAG_RELOAD;

            HINTERNET hConnect = InternetConnectA(hInternet, host, port, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
            if (!hConnect) {
                InternetCloseHandle(hInternet);
                return "{}";
            }

            HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", path, NULL, NULL, NULL, flags, 0);
            if (!hRequest) {
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{}";
            }

            std::string headers = "Content-Type: application/json\r\nUser-Agent: JoystEnclave-Cpp/2.0\r\n";
            std::string body = json_payload;

            BOOL bSend = HttpSendRequestA(hRequest, headers.c_str(), (DWORD)headers.length(), (LPVOID)body.c_str(), (DWORD)body.length());
            if (!bSend) {
                InternetCloseHandle(hRequest);
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{}";
            }

            std::string response;
            char buffer[4096];
            DWORD bytesRead = 0;
            while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
                buffer[bytesRead] = 0;
                response += buffer;
            }

            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            return response;
        }

        std::string ExtractJsonValue(const std::string& json, const std::string& key) {
            std::string searchKey = "\"" + key + "\":\"";
            size_t pos = json.find(searchKey);
            if (pos != std::string::npos) {
                size_t start = pos + searchKey.length();
                size_t end = json.find("\"", start);
                if (end != std::string::npos) {
                    return json.substr(start, end - start);
                }
            }
            std::string searchBool = "\"" + key + "\":";
            pos = json.find(searchBool);
            if (pos != std::string::npos) {
                size_t start = pos + searchBool.length();
                while (start < json.length() && (json[start] == ' ' || json[start] == '\t')) start++;
                if (json.compare(start, 4, "true") == 0) return "true";
                if (json.compare(start, 5, "false") == 0) return "false";
            }
            return "";
        }

        std::string ExtractFirstNotification(const std::string& json) {
            size_t notifsPos = json.find("\"notifications\":");
            if (notifsPos == std::string::npos) return "";

            std::string titleKey = "\"title\":\"";
            std::string msgKey = "\"message\":\"";

            size_t titlePos = json.find(titleKey, notifsPos);
            size_t msgPos = json.find(msgKey, notifsPos);

            if (titlePos != std::string::npos && msgPos != std::string::npos) {
                size_t tStart = titlePos + titleKey.length();
                size_t tEnd = json.find("\"", tStart);
                std::string title = (tEnd != std::string::npos) ? json.substr(tStart, tEnd - tStart) : "ANNOUNCEMENT";

                size_t mStart = msgPos + msgKey.length();
                size_t mEnd = json.find("\"", mStart);
                std::string message = (mEnd != std::string::npos) ? json.substr(mStart, mEnd - mStart) : "";

                if (!message.empty()) {
                    return title + "\n\n" + message;
                }
            }
            return "";
        }

        // ⚡ REAL-TIME LIVE BACKGROUND WATCHDOG:
        // Continuously polls server every 3s. If maintenance / ban / warning is triggered live while EXE is running,
        // it instantly displays a popup and terminates the app!
        void StartLiveHeartbeatWatchdog() {
            std::thread([this]() {
                while (true) {
                    std::this_thread::sleep_for(std::chrono::seconds(3));
                    try {
                        std::string payload = "{\"app_name\":\"" + this->name + "\",\"app_token\":\"" + this->token + "\",\"hwid\":\"" + this->hwid + "\",\"username\":\"" + this->user_data.username + "\",\"sessionid\":\"" + this->sessionid + "\"}";
                        std::string res = this->HttpPost("/api/v1/client/check", payload);

                        if (res.empty() || res == "{}") continue;

                        if (this->ExtractJsonValue(res, "success") == "false") {
                            std::string msg = this->ExtractJsonValue(res, "message");
                            if (msg.empty()) msg = "🚨 Application has been placed into maintenance mode or access revoked by administrator.";
                            bool is_maint = (this->ExtractJsonValue(res, "is_maintenance") == "true" || res.find("\"is_maintenance\":true") != std::string::npos);

                            std::string title = is_maint ? "JOYST - APPLICATION MAINTENANCE" : "JOYST - SECURITY ALERT";
                            MessageBoxA(NULL, msg.c_str(), title.c_str(), MB_ICONWARNING | MB_TOPMOST);
                            ExitProcess(0);
                        }

                        // Check for live broadcast announcements / warnings:
                        std::string liveNotif = this->ExtractFirstNotification(res);
                        if (!liveNotif.empty() && liveNotif != last_shown_notification) {
                            last_shown_notification = liveNotif;
                            MessageBoxA(NULL, liveNotif.c_str(), "JOYST NOTIFICATION", MB_ICONINFORMATION | MB_TOPMOST);
                        }
                    } catch (...) {}
                }
            }).detach();
        }

    public:
        user_data_class user_data;
        response_class response;

        api(std::string name, std::string token, std::string version = "1.0", std::string url = "https://joystauth.cc") {
            this->name = name;
            this->token = token;
            this->version = version;
            this->url = url;
            this->hwid = GetHwid();

            if (SecurityShield::CheckDebugger() || SecurityShield::ScanAndKillBlacklist() || SecurityShield::CheckVirtualMachine()) {
                ExitProcess(0);
            }
            SecurityShield::StartWatchdog();

            // ⚡ Startup initialization
            this->init();

            // ⚡ Launch real-time background watchdog
            this->StartLiveHeartbeatWatchdog();
        }

        void init(bool auto_handle_maintenance_and_popup = true) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"hwid\":\"" + hwid + "\"}";
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
                if (msg.empty()) msg = "Failed to connect to authentication server.";
                this->response.message = msg;
                this->response.is_maintenance = (ExtractJsonValue(res, "is_maintenance") == "true" || res.find("\"is_maintenance\":true") != std::string::npos);

                if (auto_handle_maintenance_and_popup) {
                    std::string title = this->response.is_maintenance ? "JOYST - APPLICATION MAINTENANCE" : "JOYST - ACCESS BLOCKED";
                    MessageBoxA(NULL, this->response.message.c_str(), title.c_str(), MB_ICONWARNING | MB_TOPMOST);
                    ExitProcess(0);
                }
            }
        }

        bool login(std::string username, std::string password) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(false); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
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
                if (msg.empty()) msg = "Invalid username or password.";
                this->response.message = msg;
                return false;
            }
        }

        bool license(std::string key) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(false); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"license_key\":\"" + key + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
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
                if (msg.empty()) msg = "Invalid license key.";
                this->response.message = msg;
                return false;
            }
        }

        std::string var(std::string var_name) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
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
