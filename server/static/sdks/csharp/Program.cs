using System;
using System.IO;
using System.Threading.Tasks;
using JoystAuth;

namespace DemoApp
{
    class Program
    {
        // =========================================================================
        // PRE-CONFIGURED JOYST CORPORATION AUTH CREDENTIALS
        // =========================================================================
        private const string APP_NAME    = "JOYST EXTERNAL";
        private const string OWNER_ID    = "joyst_e14d1a2a6b7b";
        private const string APP_SECRET  = "sec_b95d0d61d543bf591446c03de9625c9c";
        private const string APP_VERSION = "1.0";
        private const string API_URL     = "http://127.0.0.1:8000";

        static async Task Main(string[] args)
        {
            Console.Title = $"{APP_NAME} v{APP_VERSION} - Joyst Protected Client";

            PrintBanner();

            var auth = new api(APP_NAME, OWNER_ID, APP_SECRET, APP_VERSION, API_URL);

            Console.ForegroundColor = ConsoleColor.Cyan;
            Console.WriteLine($"[*] PC Hardware ID (HWID): {auth.hwid}");
            Console.WriteLine($"[*] Connecting to Joyst Auth Gateway for '{APP_NAME}'...");
            Console.ResetColor();

            bool initOk = await auth.init();
            if (!initOk)
            {
                Console.ForegroundColor = ConsoleColor.Red;
                Console.WriteLine($"\n[-] Gateway Initialization Failed: {auth.response.message}");
                Console.WriteLine("    Ensure your Joyst Auth Server is online at http://127.0.0.1:8000");
                Console.ResetColor();
                Console.WriteLine("\nPress any key to exit...");
                Console.ReadKey();
                return;
            }

            Console.ForegroundColor = ConsoleColor.Green;
            Console.WriteLine($"[+] Gateway Handshake Verified! [Session: {auth.sessionid?.Substring(0, 8)}...]");
            Console.ResetColor();

            while (true)
            {
                Console.WriteLine("\n==================================================");
                Console.ForegroundColor = ConsoleColor.White;
                Console.WriteLine($"       {APP_NAME.ToUpper()} - AUTHENTICATION MENU");
                Console.ResetColor();
                Console.WriteLine("  [1] 🔑 Login (Username & Password)");
                Console.WriteLine("  [2] 📝 Register New Account (Username, Pass & Key)");
                Console.WriteLine("  [3] 🎫 Login with License Key Only");
                Console.WriteLine("  [4] ☁️ Fetch Encrypted Cloud Variable (Zero-Leak)");
                Console.WriteLine("  [5] 👤 View User Profile & Subscription Expiry");
                Console.WriteLine("  [6] ❌ Exit");
                Console.WriteLine("==================================================");
                Console.Write("Select Option [1-6]: ");

                string? choice = Console.ReadLine()?.Trim();

                if (choice == "1")
                {
                    Console.Write("\nUsername: ");
                    string user = Console.ReadLine()?.Trim() ?? "";
                    Console.Write("Password: ");
                    string pass = Console.ReadLine()?.Trim() ?? "";

                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.WriteLine("[*] Verifying credentials & Motherboard HWID lock...");
                    Console.ResetColor();

                    if (await auth.login(user, pass))
                    {
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"\n✅ [ACCESS GRANTED] Welcome, {auth.user_data.username}!");
                        Console.WriteLine($"   💎 Subscription: {auth.user_data.subscription}");
                        Console.WriteLine($"   ⏳ Expiry Date:   {auth.user_data.expiry}");
                        Console.WriteLine($"   🔒 Locked HWID:  {auth.user_data.hwid.Substring(0, 16)}...");
                        Console.WriteLine($"   🌐 Client IP:    {auth.user_data.ip}");
                        Console.ResetColor();
                    }
                    else
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine($"\n❌ [ACCESS DENIED] {auth.response.message}");
                        Console.ResetColor();
                    }
                }
                else if (choice == "2")
                {
                    Console.Write("\nNew Username: ");
                    string user = Console.ReadLine()?.Trim() ?? "";
                    Console.Write("New Password: ");
                    string pass = Console.ReadLine()?.Trim() ?? "";
                    Console.Write("License Key (e.g. JOYST-...): ");
                    string key = Console.ReadLine()?.Trim() ?? "";

                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.WriteLine("[*] Redeeming license and locking account to this computer...");
                    Console.ResetColor();

                    if (await auth.register(user, pass, key))
                    {
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"\n✅ [REGISTER SUCCESS] Account activated for {auth.user_data.username}!");
                        Console.WriteLine($"   💎 Subscription: {auth.user_data.subscription}");
                        Console.WriteLine($"   ⏳ Expiry Date:   {auth.user_data.expiry}");
                        Console.ResetColor();
                    }
                    else
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine($"\n❌ [REGISTER FAILED] {auth.response.message}");
                        Console.ResetColor();
                    }
                }
                else if (choice == "3")
                {
                    Console.Write("\nLicense Key: ");
                    string key = Console.ReadLine()?.Trim() ?? "";

                    Console.ForegroundColor = ConsoleColor.Cyan;
                    Console.WriteLine("[*] Authenticating license key on Joyst gateway...");
                    Console.ResetColor();

                    if (await auth.license(key))
                    {
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"\n✅ [LICENSE VALID] Welcome {auth.user_data.username}!");
                        Console.WriteLine($"   💎 Subscription: {auth.user_data.subscription}");
                        Console.WriteLine($"   ⏳ Expiry Date:   {auth.user_data.expiry}");
                        Console.ResetColor();
                    }
                    else
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine($"\n❌ [LICENSE FAILED] {auth.response.message}");
                        Console.ResetColor();
                    }
                }
                else if (choice == "4")
                {
                    Console.Write("\nCloud Variable Name (e.g. GAME_OFFSET): ");
                    string varName = Console.ReadLine()?.Trim() ?? "";

                    string val = await auth.var(varName);
                    if (auth.response.success)
                    {
                        Console.ForegroundColor = ConsoleColor.Green;
                        Console.WriteLine($"\n✅ [CLOUD VARIABLE] {varName} = '{val}'");
                        Console.ResetColor();
                    }
                    else
                    {
                        Console.ForegroundColor = ConsoleColor.Red;
                        Console.WriteLine($"\n❌ [FETCH FAILED] {auth.response.message}");
                        Console.ResetColor();
                    }
                }
                else if (choice == "5")
                {
                    if (string.IsNullOrEmpty(auth.user_data.username))
                    {
                        Console.ForegroundColor = ConsoleColor.Yellow;
                        Console.WriteLine("\n[!] Please login first (Option 1 or 3).");
                        Console.ResetColor();
                    }
                    else
                    {
                        Console.ForegroundColor = ConsoleColor.Cyan;
                        Console.WriteLine("\n==================================================");
                        Console.WriteLine("              ACTIVE USER PROFILE                 ");
                        Console.WriteLine("==================================================");
                        Console.WriteLine($"   Username:     {auth.user_data.username}");
                        Console.WriteLine($"   Tier / Rank:  {auth.user_data.subscription}");
                        Console.WriteLine($"   Expires At:   {auth.user_data.expiry}");
                        Console.WriteLine($"   Bound HWID:   {auth.user_data.hwid}");
                        Console.WriteLine($"   Session IP:   {auth.user_data.ip}");
                        Console.WriteLine("==================================================");
                        Console.ResetColor();
                    }
                }
                else if (choice == "6")
                {
                    Console.WriteLine("\n[+] Exiting application. Goodbye!");
                    break;
                }
                else
                {
                    Console.ForegroundColor = ConsoleColor.Yellow;
                    Console.WriteLine("[!] Invalid option. Please select 1 through 6.");
                    Console.ResetColor();
                }
            }
        }

        static void PrintBanner()
        {
            Console.ForegroundColor = ConsoleColor.Red;
            Console.WriteLine(@"
    █████████   ███████████ █████ █████   █████████ 
   ███░░░░░███ ░░░░░░███░░░░░███ ░░███   ███░░░░░███
  ░███    ░░░       ░███    ░███  ░███  ░███    ░░░ 
  ░░█████████       ░███    ░███  ░███  ░░█████████ 
   ░░░░░░░░███      ░███    ░███  ░███   ░░░░░░░░███
   ███    ░███      ░███    ░███  ░███   ███    ░███
  ░░█████████       █████   ░░████████  ░░█████████ 
   ░░░░░░░░░       ░░░░░     ░░░░░░░░    ░░░░░░░░░  
                JOYST EXTERNAL v1.0
            Zero-Leak Security Architecture
");
            Console.ResetColor();
        }
    }
}
