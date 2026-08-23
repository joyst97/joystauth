#include <iostream>
#include "JoystAuth.hpp"

int main() {
    std::cout << "==================================================\n";
    std::cout << "       JOYST AUTH - C++ NATIVE CLIENT DEMO        \n";
    std::cout << "==================================================\n";

    // ⚡ Clean 2-parameter init
    JoystAuth::api auth("Apex VVIP Private", "sec_demo_master_token_69");

    std::cout << "[+] Detected Motherboard HWID: " << auth.get_hwid() << "\n";
    std::cout << "[*] Initializing session with server...\n";

    if (auth.init()) {
        std::cout << "[+] Successfully connected to Joyst Sentinel!\n\n";
        
        std::cout << "Enter username: ";
        std::string user;
        std::cin >> user;

        std::cout << "Enter password: ";
        std::string pass;
        std::cin >> pass;

        if (auth.login(user, pass)) {
            std::cout << "\n✅ " << auth.response.message << "\n";
            std::cout << "[+] User: " << auth.user_data.username << "\n";
            std::cout << "[+] Subscription: " << auth.user_data.subscription << "\n";
        } else {
            std::cout << "\n❌ " << auth.response.message << "\n";
        }
    } else {
        std::cout << "[-] " << auth.response.message << "\n";
    }

    std::cout << "\nPress Enter to exit...";
    std::cin.ignore();
    std::cin.get();
    return 0;
}
