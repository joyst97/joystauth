#include <iostream>
#include "AuthClient.hpp"

int main() {
    std::cout << "==================================================\n";
    std::cout << "       ZERO-LEAK AUTH - C++ CLIENT DEMO           \n";
    std::cout << "==================================================\n";

    std::string app_name = "DemoApp";
    std::string app_secret = "demo-secret-key-1234567890abcdef";
    std::string server_url = "http://127.0.0.1:8000";

    CustomAuth::AuthClient auth(app_name, app_secret, "1.0.0", server_url);
    std::cout << "[+] Detected HWID: " << auth.GetHwidString() << "\n";
    std::cout << "[*] Initializing session with server...\n";

    if (auth.Init()) {
        std::cout << "[+] Successfully connected to Auth Server!\n\n";
        
        std::cout << "Enter username: ";
        std::string user;
        std::cin >> user;

        std::cout << "Enter password: ";
        std::string pass;
        std::cin >> pass;

        auto res = auth.Login(user, pass);
        if (res.success) {
            std::cout << "\n[+] Welcome " << res.user_info.username << "!\n";
            std::cout << "[+] Subscription: " << res.user_info.subscription << "\n";
        } else {
            std::cout << "\n[-] Error: " << res.message << "\n";
        }
    } else {
        std::cout << "[-] Failed to connect to server. Is the auth server running?\n";
    }

    std::cout << "\nPress Enter to exit...";
    std::cin.ignore();
    std::cin.get();
    return 0;
}
