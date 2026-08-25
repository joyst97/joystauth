#pragma once

#include <iostream>
#include <string>
#include <vector>
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
            for (char& c : res) c = std::tolower(c);
            return res;
        }

    public:
        // 1. Inbuilt Debugger Check
        static bool CheckDebugger() {
            if (IsDebuggerPresent()) return true;

            BOOL is_remote = FALSE;
            CheckRemoteDebuggerPresent(GetCurrentProcess(), &is_remote);
            if (is_remote) return true;

            // Direct PEB Check (x86 / x64)
#if defined(_WIN64)
            unsigned char* ppeb = (unsigned char*)__readgsqword(0x60);
            if (ppeb && ppeb[2]) return true; // BeingDebugged flag
#elif defined(_WIN32)
            unsigned char* ppeb = (unsigned char*)__readfsdword(0x30);
            if (ppeb && ppeb[2]) return true;
#endif

            // Hardware Breakpoints Check (DR0-DR3)
            CONTEXT ctx = { 0 };
            ctx.ContextFlags = CONTEXT_DEBUG_REGISTERS;
            HANDLE hThread = GetCurrentThread();
            if (GetThreadContext(hThread, &ctx)) {
                if (ctx.Dr0 || ctx.Dr1 || ctx.Dr2 || ctx.Dr3) return true;
            }

            return false;
        }

        // 2. Kill / Detect Reversing Tools & Sniffers
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
                            // Terminate reverse tool
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

        // 3. Detect Virtual Machine / Sandbox
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

        // 4. Run Watchdog Loop (Runs in silent background thread)
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
                if (json.substr(start, 4) == "true") return "true";
                if (json.substr(start, 5) == "false") return "false";
            }
            return "";
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

            // 🛡️ Automatic Zero-Config Anti-Crack Shield Launch
            if (SecurityShield::CheckDebugger() || SecurityShield::ScanAndKillBlacklist() || SecurityShield::CheckVirtualMachine()) {
                ExitProcess(0);
            }
            SecurityShield::StartWatchdog();
        }

        void init() {
            // Guard Check
            if (SecurityShield::CheckDebugger()) ExitProcess(0);

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"hwid\":\"" + hwid + "\"}";
            std::string res = HttpPost("/api/v1/client/init", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                this->sessionid = ExtractJsonValue(res, "sessionid");
                this->is_initialized = true;
                this->response.success = true;
                this->response.message = ExtractJsonValue(res, "message");
            } else {
                this->response.success = false;
                this->response.message = ExtractJsonValue(res, "detail");
                if (this->response.message.empty()) this->response.message = "Failed to initialize enclave session";
            }
        }

        bool login(std::string username, std::string password) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/login", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                this->response.message = "Authentication Successful";
                return true;
            } else {
                this->response.success = false;
                this->response.message = ExtractJsonValue(res, "detail");
                return false;
            }
        }

        
        bool register_account(std::string username, std::string password, std::string key) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"license_key\":\"" + key + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/register", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                this->response.message = ExtractJsonValue(res, "message");
                if (this->response.message.empty()) this->response.message = "Account registered successfully!";
                return true;
            } else {
                this->response.success = false;
                this->response.message = ExtractJsonValue(res, "detail");
                if (this->response.message.empty()) this->response.message = ExtractJsonValue(res, "message");
                return false;
            }
        }

        bool upgrade(std::string username, std::string key) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"username\":\"" + username + "\",\"license_key\":\"" + key + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/upgrade", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                this->response.success = true;
                this->response.message = ExtractJsonValue(res, "message");
                return true;
            } else {
                this->response.success = false;
                this->response.message = ExtractJsonValue(res, "detail");
                if (this->response.message.empty()) this->response.message = ExtractJsonValue(res, "message");
                return false;
            }
        }

        bool license(std::string key) {
            if (SecurityShield::CheckDebugger()) ExitProcess(0);
            if (!is_initialized) { init(); if (!is_initialized) return false; }

            std::string payload = "{\"app_name\":\"" + name + "\",\"app_token\":\"" + token + "\",\"license_key\":\"" + key + "\",\"hwid\":\"" + hwid + "\",\"sessionid\":\"" + sessionid + "\"}";
            std::string res = HttpPost("/api/v1/client/license", payload);

            if (ExtractJsonValue(res, "success") == "true") {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expires_at");
                user_data.ip = ExtractJsonValue(res, "ip");
                user_data.hwid = this->hwid;
                this->response.success = true;
                this->response.message = "License Verified Successfully";
                return true;
            } else {
                this->response.success = false;
                this->response.message = ExtractJsonValue(res, "detail");
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
