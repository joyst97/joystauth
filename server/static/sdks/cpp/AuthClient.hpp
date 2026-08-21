#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <atomic>
#include <windows.h>
#include <wininet.h>
#include <wincrypt.h>
#include <tlhelp32.h>

#pragma comment(lib, "wininet.lib")
#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "advapi32.lib")

namespace JoystAuth {

    struct user_data_class {
        std::string username = "";
        std::string subscription = "";
        std::string expiry = "";
        std::string timeleft = "";
        std::string hwid = "";
        std::string ip = "";
    };

    struct response_class {
        bool success = false;
        std::string message = "";
    };

    class api {
    private:
        std::string name;
        std::string ownerid;
        std::string secret;
        std::string version;
        std::string url;
        std::string sessionid;
        std::string enckey;
        std::string hwid;
        bool is_initialized = false;
        std::atomic<bool> watchdog_running{false};

        // ================= ANTI-DEBUG & REVERSE ENGINEERING SHIELD =================
        void PerformZeroCpuSecurityCheck() {
            // 1. IsDebuggerPresent WinAPI Check (Instant 0.0001ms check)
            if (IsDebuggerPresent()) {
                SecurityAlertTrigger("Debugger Attached (IsDebuggerPresent)", "Debugger");
                ExitProcess(0);
            }

            // 2. CheckRemoteDebuggerPresent Native Kernel Check
            BOOL isRemoteDebugger = FALSE;
            CheckRemoteDebuggerPresent(GetCurrentProcess(), &isRemoteDebugger);
            if (isRemoteDebugger) {
                SecurityAlertTrigger("Remote Debugger Attached", "KernelDebugger");
                ExitProcess(0);
            }

            // 3. Fast Process Name Scanner for Reversing Tools
            const std::vector<std::string> blacklisted_processes = {
                "x64dbg.exe", "x32dbg.exe", "ida.exe", "ida64.exe", 
                "httpdebuggerui.exe", "fiddler.exe", "wireshark.exe", 
                "cheatengine-x86_64.exe", "cheatengine-i386.exe", "scylla.exe", 
                "processhacker.exe", "dnspy.exe", "megadumper.exe"
            };

            HANDLE hSnapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if (hSnapshot != INVALID_HANDLE_VALUE) {
                PROCESSENTRY32 pe32;
                pe32.dwSize = sizeof(PROCESSENTRY32);
                if (Process32First(hSnapshot, &pe32)) {
                    do {
                        std::string currentProc = pe32.szExeFile;
                        for (auto& c : currentProc) c = tolower(c);

                        for (const auto& bl : blacklisted_processes) {
                            if (currentProc.find(bl) != std::string::npos) {
                                CloseHandle(hSnapshot);
                                SecurityAlertTrigger("Disallowed process running: " + currentProc, "ReversingTool");
                                ExitProcess(0);
                            }
                        }
                    } while (Process32Next(hSnapshot, &pe32));
                }
                CloseHandle(hSnapshot);
            }
        }

        void SecurityAlertTrigger(const std::string& reason, const std::string& threat) {
            std::string payload = "{\"sessionid\":\"" + sessionid + "\",\"type\":\"security_alert\",\"reason\":\"" + reason + "\",\"threat\":\"" + threat + "\"}";
            HttpPost("/api/v1/client/gateway", payload);
        }

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
            HINTERNET hInternet = InternetOpenA("JoystCorp-CppShield/2.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
            if (!hInternet) return "{}";

            URL_COMPONENTSA urlComp;
            memset(&urlComp, 0, sizeof(urlComp));
            urlComp.dwStructSize = sizeof(urlComp);
            char host[256] = {0};
            char path[512] = {0};
            urlComp.lpszHostName = host;
            urlComp.dwHostNameLength = sizeof(host);
            urlComp.lpszUrlPath = path;
            urlComp.dwUrlPathLength = sizeof(path);

            InternetCrackUrlA(full_url.c_str(), 0, 0, &urlComp);

            INTERNET_PORT port = urlComp.nPort ? urlComp.nPort : (urlComp.nScheme == INTERNET_SCHEME_HTTPS ? INTERNET_DEFAULT_HTTPS_PORT : INTERNET_DEFAULT_HTTP_PORT);
            HINTERNET hConnect = InternetConnectA(hInternet, host, port, NULL, NULL, INTERNET_SERVICE_HTTP, 0, 0);
            if (!hConnect) {
                InternetCloseHandle(hInternet);
                return "{}";
            }

            DWORD flags = INTERNET_FLAG_RELOAD | INTERNET_FLAG_NO_CACHE_WRITE;
            if (urlComp.nScheme == INTERNET_SCHEME_HTTPS) flags |= INTERNET_FLAG_SECURE;

            HINTERNET hRequest = HttpOpenRequestA(hConnect, "POST", path, NULL, NULL, NULL, flags, 0);
            if (!hRequest) {
                InternetCloseHandle(hConnect);
                InternetCloseHandle(hInternet);
                return "{}";
            }

            const char* headers = "Content-Type: application/json\r\n";
            HttpSendRequestA(hRequest, headers, (DWORD)strlen(headers), (LPVOID)json_payload.c_str(), (DWORD)json_payload.length());

            std::string responseStr;
            char buffer[4096];
            DWORD bytesRead = 0;
            while (InternetReadFile(hRequest, buffer, sizeof(buffer) - 1, &bytesRead) && bytesRead > 0) {
                buffer[bytesRead] = '\0';
                responseStr += buffer;
            }

            InternetCloseHandle(hRequest);
            InternetCloseHandle(hConnect);
            InternetCloseHandle(hInternet);
            return responseStr;
        }

        std::string ExtractJsonValue(const std::string& json, const std::string& key) {
            std::string target = "\"" + key + "\":\"";
            size_t pos = json.find(target);
            if (pos != std::string::npos) {
                pos += target.length();
                size_t endPos = json.find("\"", pos);
                if (endPos != std::string::npos) {
                    return json.substr(pos, endPos - pos);
                }
            }
            return "";
        }

    public:
        user_data_class user_data;
        response_class response;

        api(std::string name, std::string ownerid, std::string secret, std::string ver = "1.0", std::string server_url = "https://joystauth.cc")
            : name(name), ownerid(ownerid), secret(secret), version(ver), url(server_url) {
            hwid = GetHwid();
            PerformZeroCpuSecurityCheck();
        }

        ~api() {
            watchdog_running = false;
        }

        bool init() {
            PerformZeroCpuSecurityCheck();
            std::string payload = "{\"name\":\"" + name + "\",\"ownerid\":\"" + ownerid + "\",\"secret\":\"" + secret + "\",\"hwid\":\"" + hwid + "\",\"version\":\"" + version + "\"}";
            std::string res = HttpPost("/api/v1/client/init", payload);

            if (res.find("\"success\":true") != std::string::npos || res.find("\"success\": true") != std::string::npos) {
                sessionid = ExtractJsonValue(res, "sessionid");
                is_initialized = true;
                response.success = true;
                response.message = "Initialized successfully";
                return true;
            }
            response.success = false;
            response.message = "Initialization failed: " + ExtractJsonValue(res, "message");
            return false;
        }

        bool login(std::string username, std::string password) {
            PerformZeroCpuSecurityCheck();
            if (!is_initialized && !init()) return false;

            std::string payload = "{\"sessionid\":\"" + sessionid + "\",\"type\":\"login\",\"username\":\"" + username + "\",\"password\":\"" + password + "\",\"hwid\":\"" + hwid + "\"}";
            std::string res = HttpPost("/api/v1/client/gateway", payload);

            if (res.find("\"success\":true") != std::string::npos || res.find("\"success\": true") != std::string::npos) {
                user_data.username = username;
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expiry");
                user_data.hwid = hwid;
                response.success = true;
                response.message = "Login successful";
                return true;
            }

            response.success = false;
            response.message = ExtractJsonValue(res, "message");
            if (response.message.empty()) response.message = "Login verification failed";
            return false;
        }

        bool license(std::string key) {
            PerformZeroCpuSecurityCheck();
            if (!is_initialized && !init()) return false;

            std::string payload = "{\"sessionid\":\"" + sessionid + "\",\"type\":\"license\",\"key\":\"" + key + "\",\"hwid\":\"" + hwid + "\"}";
            std::string res = HttpPost("/api/v1/client/gateway", payload);

            if (res.find("\"success\":true") != std::string::npos || res.find("\"success\": true") != std::string::npos) {
                user_data.username = ExtractJsonValue(res, "username");
                user_data.subscription = ExtractJsonValue(res, "subscription");
                user_data.expiry = ExtractJsonValue(res, "expiry");
                user_data.hwid = hwid;
                response.success = true;
                response.message = "License authenticated successfully";
                return true;
            }

            response.success = false;
            response.message = ExtractJsonValue(res, "message");
            return false;
        }

        std::string var(std::string var_name) {
            PerformZeroCpuSecurityCheck();
            if (!is_initialized) return "";

            std::string payload = "{\"sessionid\":\"" + sessionid + "\",\"type\":\"var\",\"varid\":\"" + var_name + "\",\"hwid\":\"" + hwid + "\"}";
            std::string res = HttpPost("/api/v1/client/gateway", payload);
            return ExtractJsonValue(res, "value");
        }

        // ================= BACKGROUND HEARTBEAT WATCHDOG =================
        void start_heartbeat(int interval_seconds = 30) {
            if (watchdog_running) return;
            watchdog_running = true;

            std::thread([this, interval_seconds]() {
                while (watchdog_running) {
                    std::this_thread::sleep_for(std::chrono::seconds(interval_seconds));
                    if (!watchdog_running) break;

                    PerformZeroCpuSecurityCheck();

                    std::string payload = "{\"sessionid\":\"" + sessionid + "\",\"type\":\"heartbeat\",\"hwid\":\"" + hwid + "\"}";
                    std::string res = HttpPost("/api/v1/client/gateway", payload);

                    if (res.find("\"success\":true") == std::string::npos && res.find("\"success\": true") == std::string::npos) {
                        // Tampering or session expired on server side -> Terminate Process Immediately
                        ExitProcess(0);
                    }
                }
            }).detach();
        }

        std::string get_hwid() const { return hwid; }
    };
}
