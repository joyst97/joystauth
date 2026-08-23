#pragma once

#include <iostream>
#include <string>
#include <vector>
#include <windows.h>
#include <wininet.h>
#include <wincrypt.h>

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
            HINTERNET hInternet = InternetOpenA("JoystCorp-Cpp/1.0", INTERNET_OPEN_TYPE_DIRECT, NULL, NULL, 0);
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

            INTERNET_PORT port = urlComp.nPort ? urlComp.nPort : INTERNET_DEFAULT_HTTP_PORT;
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
            HttpSendRequestA(hRequest, headers, strlen(headers), (LPVOID)json_payload.c_str(), (DWORD)json_payload.length());

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

    public:
        user_data_class user_data;
        response_class response;

        // ⚡ Clean Constructor: App Name + Master App Token
        api(std::string name, std::string token, std::string ver = "1.0", std::string server_url = "https://joystauth.cc")
            : name(name), token(token), version(ver), url(server_url) {
            hwid = GetHwid();
        }

        bool init() {
            std::string payload = "{\"name\":\"" + name + "\",\"token\":\"" + token + "\",\"hwid\":\"" + hwid + "\",\"version\":\"" + version + "\"}";
            std::string res = HttpPost("/api/v1/client/init", payload);

            if (res.find("\"success\":true") != std::string::npos || res.find("\"success\": true") != std::string::npos) {
                size_t tokenPos = res.find("\"sessionid\":\"");
                if (tokenPos != std::string::npos) {
                    tokenPos += 13;
                    size_t endPos = res.find("\"", tokenPos);
                    sessionid = res.substr(tokenPos, endPos - tokenPos);
                }
                is_initialized = true;
                response.success = true;
                response.message = "Initialized successfully";
                return true;
            }

            // Inbuilt Automatic Maintenance Killswitch
            if (res.find("maintenance") != std::string::npos || res.find("is_maintenance\":true") != std::string::npos) {
                response.success = false;
                response.is_maintenance = true;
                response.message = "Application is currently under maintenance! Execution blocked.";
                MessageBoxA(NULL, "Application is currently under maintenance!\nExecution forcefully terminated by developer.", "EMERGENCY MAINTENANCE", MB_OK | MB_ICONSTOP | MB_TOPMOST);
                ExitProcess(0);
            }

            response.success = false;
            response.message = "Initialization failed";
            return false;
        }

        bool login(std::string username, std::string password) {
            if (!is_initialized && !init()) return false;
            std::string payload = "{\"name\":\"" + name + "\",\"token\":\"" + token + "\",\"hwid\":\"" + hwid + "\",\"username\":\"" + username + "\",\"password\":\"" + password + "\"}";
            std::string res = HttpPost("/api/v1/client/gateway", payload);

            if (res.find("\"success\":true") != std::string::npos || res.find("\"success\": true") != std::string::npos) {
                user_data.username = username;
                user_data.subscription = "VIP Tier";
                response.success = true;
                response.message = "Logged in successfully!";
                return true;
            }

            if (res.find("maintenance") != std::string::npos) {
                MessageBoxA(NULL, "Application is currently under maintenance!", "EMERGENCY MAINTENANCE", MB_OK | MB_ICONSTOP | MB_TOPMOST);
                ExitProcess(0);
            }

            response.success = false;
            response.message = "Invalid username or password.";
            return false;
        }

        std::string get_hwid() const { return hwid; }
    };
}
