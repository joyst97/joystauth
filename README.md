# ⚡ JOYST CORPORATION - ZERO-LEAK AUTHENTICATION & LICENSING INFRASTRUCTURE

Exact KeyAuth parity authentication & licensing infrastructure with **Name, Owner ID, Secret, and Version** support, strict **HWID locking**, **IP logging**, cyber-dark Web Dashboard, Discord Bot, and multi-language SDKs for **Python, C#, C++, Java, and Rust**.

---

## 🌟 KeyAuth Parity Parameters & Logic

Every application created in Joyst Corporation has exact KeyAuth parameters:
- **`name`**: Application Name (e.g. `JoystApp` or `MySoftware`)
- **`ownerid`**: Unique Admin Owner ID (e.g. `joyst_owner_...`)
- **`secret`**: Cryptographically secure Application Secret Key (`sec_...`)
- **`version`**: Application version (e.g. `1.0`)
- **`hwid`**: Hardware Identifier (Strictly locked to the user's PC upon 1st login/activation)

---

## 🚀 Quick Start (Kaise Use Karein)

### 1. Web Dashboard & Server Start Karna
Double click **`run_server.bat`** (or select option 1 in **`start_all.bat`**):
- Web Dashboard automatically browser me open ho jayega **`http://localhost:8000`** par.
- **Default Admin Login**:
  - **Username**: `admin`
  - **Password**: `admin123`

Dashboard ke header me aur Overview tab me aapka **Application Name**, **Owner ID**, **Secret**, aur **Version** 1-click copy button ke sath directly dikhega!

---

### 2. Client GUI Login Window (Python) Test Karna
Double click **`run_python_gui_demo.bat`**:
- Modern Tkinter desktop window khulegi.
- Dashboard se **⚡ Generate License** dabayein aur key generate karein (`JOYST-XXXX-XXXX-XXXX`).
- GUI me **Register** ya **Key Only** me key paste karein aur login karein!

---

### 3. C# .NET SDK
In terminal `sdks/csharp`:
```bash
dotnet run
```

---

### 4. Discord Bot
1. `discord_bot/config.json` me apna bot token daalein.
2. Double click **`run_discord_bot.bat`**.
3. Discord me slash commands use karein:
   - `/genkey` - License generate karein.
   - `/resethwid` - 1-Click HWID reset karein.
   - `/userinfo` - User details aur HWID status dekhein.
   - `/banuser` - User ban karein.
   - `/stats` - Live telemetry dekhein.

---

## 🔒 HWID Lock Security Model

- **First Login Lock**: Jab koi user pehli baar account banata hai ya login karta hai, uska hardware ID bind ho jata hai.
- **Zero Account Sharing**: Agar wahi user kisi dost ko password dega, dusra computer **`HWID Mismatch`** error ke sath reject ho jayega.
- **Instant HWID Reset**: Aap Web Dashboard se **🔄 Reset HWID** daba kar ya Discord se `/resethwid` command se instantly HWID unlock kar sakte hain.
