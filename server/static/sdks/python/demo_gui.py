import tkinter as tk
from tkinter import messagebox, ttk
from auth_client import api

class JoystAuthApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JOYST CORPORATION - Desktop Client Demo")
        self.geometry("480x640")
        self.configure(bg="#07090e")
        self.resizable(False, False)

        self.auth = None
        self.init_ui()

    def init_ui(self):
        # Header
        header_frame = tk.Frame(self, bg="#101422", height=90)
        header_frame.pack(fill="x")

        lbl_brand = tk.Label(header_frame, text="⚡ JOYST CORPORATION", font=("Inter", 16, "bold"), fg="#38bdf8", bg="#101422")
        lbl_brand.pack(pady=(16, 2))

        self.lbl_status = tk.Label(header_frame, text="Ready to connect", font=("Inter", 9), fg="#94a3b8", bg="#101422")
        self.lbl_status.pack(pady=(0, 12))

        # App Configuration Frame (KeyAuth Parameters)
        cfg_frame = tk.LabelFrame(self, text=" Application Parameters (From Dashboard) ", bg="#07090e", fg="#818cf8", font=("Inter", 9, "bold"), padx=12, pady=8)
        cfg_frame.pack(fill="x", padx=20, pady=(10, 5))

        # Row 1: App Name & Owner ID
        r1 = tk.Frame(cfg_frame, bg="#07090e")
        r1.pack(fill="x", pady=2)
        tk.Label(r1, text="App Name:", fg="#94a3b8", bg="#07090e", font=("Inter", 9), width=10, anchor="w").pack(side="left")
        self.ent_app_name = tk.Entry(r1, font=("Inter", 9), bg="#101422", fg="#fff", insertbackground="#fff")
        self.ent_app_name.insert(0, "MySoftware")
        self.ent_app_name.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Label(r1, text="Owner ID:", fg="#94a3b8", bg="#07090e", font=("Inter", 9), width=8, anchor="w").pack(side="left")
        self.ent_owner_id = tk.Entry(r1, font=("Inter", 9), bg="#101422", fg="#fff", insertbackground="#fff")
        self.ent_owner_id.insert(0, "joyst_owner")
        self.ent_owner_id.pack(side="left", fill="x", expand=True)

        # Row 2: Secret & Version
        r2 = tk.Frame(cfg_frame, bg="#07090e")
        r2.pack(fill="x", pady=2)
        tk.Label(r2, text="Secret Key:", fg="#94a3b8", bg="#07090e", font=("Inter", 9), width=10, anchor="w").pack(side="left")
        self.ent_secret = tk.Entry(r2, font=("Inter", 9), bg="#101422", fg="#fff", show="•", insertbackground="#fff")
        self.ent_secret.insert(0, "sec_demo")
        self.ent_secret.pack(side="left", fill="x", expand=True, padx=(0, 10))

        tk.Label(r2, text="Version:", fg="#94a3b8", bg="#07090e", font=("Inter", 9), width=8, anchor="w").pack(side="left")
        self.ent_version = tk.Entry(r2, font=("Inter", 9), bg="#101422", fg="#fff", insertbackground="#fff")
        self.ent_version.insert(0, "1.0")
        self.ent_version.pack(side="left", fill="x", expand=True)

        # Notebook (Tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(pady=10, padx=20, fill="both", expand=True)

        # Tab 1: User Login
        self.tab_login = tk.Frame(self.notebook, bg="#07090e")
        self.notebook.add(self.tab_login, text="User Login")
        self.build_login_tab()

        # Tab 2: Register
        self.tab_reg = tk.Frame(self.notebook, bg="#07090e")
        self.notebook.add(self.tab_reg, text="Register")
        self.build_reg_tab()

        # Tab 3: License Key Only
        self.tab_key = tk.Frame(self.notebook, bg="#07090e")
        self.notebook.add(self.tab_key, text="Key Only")
        self.build_key_tab()

    def get_api_instance(self):
        name = self.ent_app_name.get().strip()
        ownerid = self.ent_owner_id.get().strip()
        secret = self.ent_secret.get().strip()
        version = self.ent_version.get().strip() or "1.0"
        return api(name=name, ownerid=ownerid, secret=secret, version=version, url="http://127.0.0.1:8000")

    def build_login_tab(self):
        tk.Label(self.tab_login, text="Username", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(16, 2))
        self.ent_login_user = tk.Entry(self.tab_login, font=("Inter", 11), bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_login_user.pack(fill="x", padx=25, pady=(0, 10), ipady=3)

        tk.Label(self.tab_login, text="Password", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(4, 2))
        self.ent_login_pass = tk.Entry(self.tab_login, font=("Inter", 11), show="•", bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_login_pass.pack(fill="x", padx=25, pady=(0, 20), ipady=3)

        btn = tk.Button(self.tab_login, text="Sign In", font=("Inter", 11, "bold"), bg="#3b82f6", fg="#fff", activebackground="#2563eb", cursor="hand2", relief="flat", command=self.on_login)
        btn.pack(fill="x", padx=25, pady=5, ipady=6)

    def build_reg_tab(self):
        tk.Label(self.tab_reg, text="Username", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(10, 2))
        self.ent_reg_user = tk.Entry(self.tab_reg, font=("Inter", 11), bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_reg_user.pack(fill="x", padx=25, pady=(0, 6), ipady=3)

        tk.Label(self.tab_reg, text="Password", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(4, 2))
        self.ent_reg_pass = tk.Entry(self.tab_reg, font=("Inter", 11), show="•", bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_reg_pass.pack(fill="x", padx=25, pady=(0, 6), ipady=3)

        tk.Label(self.tab_reg, text="License Key", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(4, 2))
        self.ent_reg_key = tk.Entry(self.tab_reg, font=("Inter", 11), bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_reg_key.pack(fill="x", padx=25, pady=(0, 16), ipady=3)

        btn = tk.Button(self.tab_reg, text="Create Account", font=("Inter", 11, "bold"), bg="#10b981", fg="#fff", activebackground="#059669", cursor="hand2", relief="flat", command=self.on_register)
        btn.pack(fill="x", padx=25, pady=5, ipady=6)

    def build_key_tab(self):
        tk.Label(self.tab_key, text="Enter License Key", fg="#94a3b8", bg="#07090e", font=("Inter", 10, "bold")).pack(anchor="w", padx=25, pady=(24, 2))
        self.ent_lic_key = tk.Entry(self.tab_key, font=("Inter", 11), bg="#101422", fg="#fff", insertbackground="#fff", relief="flat", highlightthickness=1, highlightbackground="#222e48")
        self.ent_lic_key.pack(fill="x", padx=25, pady=(0, 20), ipady=3)

        btn = tk.Button(self.tab_key, text="Activate & Login", font=("Inter", 11, "bold"), bg="#8b5cf6", fg="#fff", activebackground="#7c3aed", cursor="hand2", relief="flat", command=self.on_key_login)
        btn.pack(fill="x", padx=25, pady=5, ipady=6)

    def on_login(self):
        user = self.ent_login_user.get().strip()
        pwd = self.ent_login_pass.get()
        if not user or not pwd:
            messagebox.showwarning("Warning", "Please enter username and password.")
            return

        client = self.get_api_instance()
        if client.login(user, pwd):
            u = client.user_data
            self.lbl_status.config(text=f"● Authenticated: {u.username}", fg="#10b981")
            messagebox.showinfo("Login Success", f"Welcome back, {u.username}!\n\nRank: {u.subscription}\nExpires: {u.expires}\nHWID: {u.hwid[:16]}...")
        else:
            self.lbl_status.config(text="● Login Failed", fg="#ef4444")
            messagebox.showerror("Login Failed", client.response.message)

    def on_register(self):
        user = self.ent_reg_user.get().strip()
        pwd = self.ent_reg_pass.get()
        key = self.ent_reg_key.get().strip()
        if not user or not pwd or not key:
            messagebox.showwarning("Warning", "All fields are required.")
            return

        client = self.get_api_instance()
        if client.register(user, pwd, key):
            self.lbl_status.config(text=f"● Registered: {user}", fg="#10b981")
            messagebox.showinfo("Registered", "Account created successfully! You can now log in.")
        else:
            self.lbl_status.config(text="● Register Failed", fg="#ef4444")
            messagebox.showerror("Registration Failed", client.response.message)

    def on_key_login(self):
        key = self.ent_lic_key.get().strip()
        if not key:
            messagebox.showwarning("Warning", "Please enter your license key.")
            return

        client = self.get_api_instance()
        if client.license(key):
            u = client.user_data
            self.lbl_status.config(text=f"● Key Active: {u.username}", fg="#10b981")
            messagebox.showinfo("License Valid", f"License Activated!\n\nUser: {u.username}\nRank: {u.subscription}\nExpiry: {u.expires}")
        else:
            self.lbl_status.config(text="● License Error", fg="#ef4444")
            messagebox.showerror("Failed", client.response.message)

if __name__ == "__main__":
    app = JoystAuthApp()
    app.mainloop()
