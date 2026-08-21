import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import os

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    cfg = {
        "token": os.environ.get("DISCORD_BOT_TOKEN", "YOUR_DISCORD_BOT_TOKEN_HERE"),
        "api_url": os.environ.get("API_URL", "https://joystauth.cc"),
        "admin_token": "YOUR_JWT_ADMIN_TOKEN_HERE",
        "default_app_id": 1,
        "guild_id": None
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                disk_cfg = json.load(f)
                cfg.update(disk_cfg)
        except Exception:
            pass
    if os.environ.get("DISCORD_BOT_TOKEN"):
        cfg["token"] = os.environ.get("DISCORD_BOT_TOKEN")
    return cfg

config = load_config()

intents = discord.Intents.default()
intents.message_content = True
from discord.ext import tasks

intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Auto-rotating Dynamic Status in DND Mode
STATUS_LIST = [
    ("watching", "🛡️ Joyst Auth Zero-Leak Security"),
    ("competing", "⚡ joystauth.cc • /help"),
    ("watching", "🔐 Managing Licenses & HWIDs"),
    ("listening", "💎 /genkey | /adduser | /stats")
]
status_index = 0

@tasks.loop(seconds=20)
async def dynamic_presence_loop():
    global status_index
    try:
        activity_type, text = STATUS_LIST[status_index % len(STATUS_LIST)]
        status_index += 1

        if activity_type == "watching":
            act = discord.Activity(type=discord.ActivityType.watching, name=text)
        elif activity_type == "listening":
            act = discord.Activity(type=discord.ActivityType.listening, name=text)
        else:
            act = discord.Activity(type=discord.ActivityType.competing, name=text)

        # DND (Do Not Disturb) Status with Custom Activity
        await bot.change_presence(status=discord.Status.dnd, activity=act)
    except Exception:
        pass

# Background Auto-Sync Slash Commands without Restart
@tasks.loop(minutes=5)
async def auto_sync_commands_loop():
    try:
        await bot.tree.sync()
        print("[JOYST CORP AUTH BOT] 🔄 Auto-synced all slash commands seamlessly in background.")
    except Exception as e:
        print(f"[JOYST AUTO SYNC NOTICE] {e}")

@bot.event
async def on_ready():
    print(f"[JOYST CORP AUTH BOT] Logged in as {bot.user.name} (ID: {bot.user.id})")
    
    # 1. Set Initial DND Presence
    act = discord.Activity(type=discord.ActivityType.watching, name="🛡️ Joyst Auth Zero-Leak Security • joystauth.cc")
    await bot.change_presence(status=discord.Status.dnd, activity=act)

    # 2. Instant First-time Global Sync
    try:
        synced = await bot.tree.sync()
        print(f"[JOYST CORP AUTH BOT] Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"[JOYST CORP AUTH BOT] Initial sync notice: {e}")

    # 3. Start Loops
    if not dynamic_presence_loop.is_running():
        dynamic_presence_loop.start()
    if not auto_sync_commands_loop.is_running():
        auto_sync_commands_loop.start()

# ==================== INTERACTIVE UI DROPDOWNS ====================

class AppSelectView(discord.ui.View):
    def __init__(self, action_type: str, action_data: dict, apps: list):
        super().__init__(timeout=60)
        self.action_type = action_type
        self.action_data = action_data
        self.apps = apps

        options = [
            discord.SelectOption(
                label=app["name"],
                description=f"App ID: {app['id']} • Version: {app.get('version', '1.0')}",
                emoji="📱",
                value=app["name"]
            )
            for app in apps[:25] # Discord max 25 options
        ]

        select = discord.ui.Select(
            placeholder="📱 Select Application from your account...",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_app = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=False)

        # 1. Action: GENKEY
        if self.action_type == "genkey":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json=self.action_data, timeout=15)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                keys = data.get("keys", [])
                embed = discord.Embed(
                    title="⚡ Joyst Auth - License Keys Generated",
                    description=f"Generated **{len(keys)}** key(s) for application **`{selected_app}`**:\n\n" + "\n".join([f"🔑 `{k}`" for k in keys]),
                    color=0xE11D48
                )
                embed.add_field(name="📱 Application", value=f"`{selected_app}`", inline=True)
                embed.add_field(name="⏳ Duration", value=f"{self.action_data['duration_days']} Days" if self.action_data['duration_days'] > 0 else "🌟 Lifetime", inline=True)
                embed.add_field(name="💎 Rank", value=f"`{self.action_data['level']}`", inline=True)
                embed.set_footer(text="Joyst Auth Enterprise • joystauth.cc")
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                await interaction.edit_original_response(content=f"❌ **Error:** {data.get('detail', 'Key generation failed')}", view=None)

        # 2. Action: ADDUSER
        elif self.action_type == "adduser":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/adduser", json=self.action_data, timeout=15)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                embed = discord.Embed(
                    title="👤 User Account Created Successfully",
                    description=f"Client **`{data['username']}`** is now active and ready to log into **`{selected_app}`**.",
                    color=0x10B981
                )
                embed.add_field(name="👤 Username", value=f"`{data['username']}`", inline=True)
                embed.add_field(name="🔑 Password", value=f"`{self.action_data['password']}`", inline=True)
                embed.add_field(name="📱 App", value=f"`{selected_app}`", inline=True)
                embed.add_field(name="💎 Rank", value=f"`{data['subscription']}`", inline=True)
                embed.add_field(name="⏳ Expiry", value=f"`{data['expires_at']}`", inline=True)
                embed.set_footer(text="Joyst Auth Enterprise • joystauth.cc")
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                await interaction.edit_original_response(content=f"❌ **Error:** {data.get('detail', 'Failed to create user')}", view=None)

# ==================== SLASH COMMANDS ====================

# Helper function to fetch developer apps
def fetch_developer_apps(discord_id: str, discord_username: str):
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/apps", json={
            "discord_id": str(discord_id),
            "discord_username": str(discord_username)
        }, timeout=15)
        if res.status_code == 200:
            return res.json().get("apps", [])
    except Exception:
        pass
    return []

# 1. /genkey
@bot.tree.command(name="genkey", description="⚡ Instantly generate license keys for your Joyst Auth Application")
@app_commands.describe(
    days="Duration in days (-1 for lifetime)",
    count="Number of keys to generate (1-50)",
    level="Subscription Level / Rank (e.g. default, VIP)",
    app="Application Name (leave blank to choose from Dropdown)"
)
async def genkey(interaction: discord.Interaction, days: int = 30, count: int = 1, level: str = "default", app: str = None):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "app_name": app,
        "count": min(max(1, count), 50),
        "duration_days": days,
        "level": level,
        "mask": "JOYST-XXXX-XXXX-XXXX"
    }

    # If app is not specified, check if developer has multiple apps and show Dropdown Menu!
    if not app:
        apps = fetch_developer_apps(str(interaction.user.id), str(interaction.user.name))
        if len(apps) > 1:
            view = AppSelectView("genkey", payload, apps)
            await interaction.followup.send("📋 **You have multiple applications!** Please select which app you want to generate keys for below:", view=view)
            return

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            app_name = data.get("app_name", "JOYST")
            dev_user = data.get("developer", interaction.user.name)
            plan = data.get("plan", "Enterprise")

            embed = discord.Embed(
                title="⚡ Joyst Auth - License Keys Generated",
                description=f"Generated **{len(keys)}** key(s) for application **`{app_name}`**:\n\n" + "\n".join([f"🔑 `{k}`" for k in keys]),
                color=0xE11D48
            )
            embed.add_field(name="📱 Application", value=f"`{app_name}`", inline=True)
            embed.add_field(name="⏳ Duration", value=f"{days} Days" if days > 0 else "🌟 Lifetime", inline=True)
            embed.add_field(name="💎 Rank / Level", value=f"`{level}`", inline=True)
            embed.add_field(name="👤 Developer", value=f"@{dev_user} ({plan})", inline=True)
            embed.set_footer(text="Joyst Auth Enterprise • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            err_msg = data.get("detail", data.get("message", "Key generation failed"))
            await interaction.followup.send(f"❌ **Notice:** {err_msg}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Connection Error:** {str(e)}", ephemeral=False)

# 2. /adduser (Username + Password Direct Creation)
@bot.tree.command(name="adduser", description="👤 Create a client User & Password directly with subscription time")
@app_commands.describe(
    username="Client username to create",
    password="Client login password",
    days="Subscription duration in days (-1 for lifetime)",
    rank="Subscription Rank/Tier (e.g. default, VIP)",
    app="Application Name (leave blank to choose from Dropdown)"
)
async def adduser(interaction: discord.Interaction, username: str, password: str, days: int = 30, rank: str = "default", app: str = None):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "app_name": app,
        "username": username.strip(),
        "password": password.strip(),
        "duration_days": days,
        "subscription_tier": rank
    }

    # If app is not specified, check if developer has multiple apps and show Dropdown Menu!
    if not app:
        apps = fetch_developer_apps(str(interaction.user.id), str(interaction.user.name))
        if len(apps) > 1:
            view = AppSelectView("adduser", payload, apps)
            await interaction.followup.send("📋 **You have multiple applications!** Please select which app to create this user in below:", view=view)
            return

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/adduser", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="👤 User Account Created Successfully",
                description=f"Client **`{data['username']}`** is now active and ready to log into **`{data['app_name']}`**.",
                color=0x10B981
            )
            embed.add_field(name="👤 Username", value=f"`{data['username']}`", inline=True)
            embed.add_field(name="🔑 Password", value=f"`{password}`", inline=True)
            embed.add_field(name="📱 App", value=f"`{data['app_name']}`", inline=True)
            embed.add_field(name="💎 Rank", value=f"`{data['subscription']}`", inline=True)
            embed.add_field(name="⏳ Expiry", value=f"`{data['expires_at']}`", inline=True)
            embed.add_field(name="💻 HWID Status", value="🟢 `Ready to Bind on 1st Login`", inline=True)
            embed.set_footer(text="Joyst Auth Enterprise • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Failed to create user')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)
@bot.tree.command(name="resethwid", description="🔄 Reset HWID lock for a specific user in your application")
@app_commands.describe(username="The client username whose HWID to reset")
async def resethwid(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/resethwid", json=payload, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🔄 HWID Reset Successful",
                description=f"Hardware ID lock for client **`{data['username']}`** in app **`{data.get('app_name', 'Active App')}`** has been cleared.\nThe user can now bind a new device on next login.",
                color=0x10B981
            )
            embed.set_footer(text="Joyst Auth Security • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'User not found')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 3. /userinfo
@bot.tree.command(name="userinfo", description="🔍 Look up a registered client's details, subscription, and HWID")
@app_commands.describe(username="Username to inspect")
async def userinfo(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/userinfo", json=payload, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            u = data["user"]
            status_text = "🚫 **BANNED**" if u["is_banned"] else "🟢 **ACTIVE**"
            embed = discord.Embed(
                title=f"👤 Client Profile: {u['username']}",
                color=0xDC2626 if u["is_banned"] else 0x10B981
            )
            embed.add_field(name="📱 App", value=f"`{u['app_name']}`", inline=True)
            embed.add_field(name="🛡️ Status", value=status_text, inline=True)
            embed.add_field(name="💎 Rank", value=f"`{u['subscription']}` (Level {u['level']})", inline=True)
            embed.add_field(name="⏳ Expiry", value=f"`{u['expires_at']}`", inline=True)
            embed.add_field(name="🌐 Last IP", value=f"`{u['last_ip']}`", inline=True)
            embed.add_field(name="💻 HWID", value=f"`{u['hwid'][:24]}...`" if len(u['hwid']) > 24 else f"`{u['hwid']}`", inline=False)
            if u["is_banned"]:
                embed.add_field(name="⚠️ Ban Reason", value=f"`{u['ban_reason']}`", inline=False)
            embed.set_footer(text="Joyst Auth Database • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'User not found')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 4. /ban
@bot.tree.command(name="ban", description="🔨 Ban a client user from logging into your applications")
@app_commands.describe(username="User to ban", reason="Reason for the ban")
async def ban(interaction: discord.Interaction, username: str, reason: str = "Banned by Admin"):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip(),
        "reason": reason.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/ban", json=payload, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🔨 User Account Banned",
                description=f"User **`{data['username']}`** has been permanently banned from authenticating.\n**Reason:** `{data['reason']}`",
                color=0xDC2626
            )
            embed.set_footer(text="Joyst Auth Shield • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'Failed to ban user')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 5. /unban
@bot.tree.command(name="unban", description="🔓 Unban a previously banned client user")
@app_commands.describe(username="User to unban")
async def unban(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/unban", json=payload, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🔓 User Unbanned",
                description=f"User **`{data['username']}`** has been restored and can now authenticate normally.",
                color=0x10B981
            )
            embed.set_footer(text="Joyst Auth Shield • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'Failed to unban user')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 6. /stats
@bot.tree.command(name="stats", description="📊 View live statistics of your applications, users, and licenses")
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name)
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/stats", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="📊 Joyst Auth - Developer Telemetry",
                description=f"Live statistics for Developer **@{data['developer']}** (`{data['plan']}` Plan):",
                color=0x6366F1
            )
            embed.add_field(name="📦 Apps", value=f"**{data['total_apps']}** ({', '.join(data['apps_list']) or 'None'})", inline=False)
            embed.add_field(name="👥 Total Users", value=f"**{data['total_users']}**", inline=True)
            embed.add_field(name="🔑 Total Keys", value=f"**{data['total_keys']}**", inline=True)
            embed.add_field(name="🟢 Unused Keys", value=f"**{data['unused_keys']}**", inline=True)
            embed.add_field(name="🚫 Banned Users", value=f"**{data['banned_users']}**", inline=True)
            embed.set_footer(text="Joyst Auth Zero-Leak Infrastructure • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Failed to fetch stats')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 7. /addreseller
@bot.tree.command(name="addreseller", description="💼 Create a new Reseller with key credits balance")
@app_commands.describe(username="Reseller username", password="Reseller dashboard password", balance="Initial key credits")
async def addreseller(interaction: discord.Interaction, username: str, password: str, balance: int = 50):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "reseller_username": username.strip(),
        "reseller_password": password.strip(),
        "balance": max(0, balance)
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/addreseller", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="💼 Reseller Account Created",
                description=f"New Reseller **`@{data['reseller_username']}`** is now active with **{data['balance']} Credits**.",
                color=0x818CF8
            )
            embed.add_field(name="💼 Reseller Username", value=f"`{data['reseller_username']}`", inline=True)
            embed.add_field(name="🔑 Password", value=f"`{password}`", inline=True)
            embed.add_field(name="💳 Credits Balance", value=f"`{data['balance']} Keys`", inline=True)
            embed.add_field(name="🌐 Reseller Portal", value="`https://joystauth.cc/reseller/login`", inline=False)
            embed.set_footer(text="Joyst Auth Enterprise Reseller System")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Failed to create reseller')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 8. /addbalance
@bot.tree.command(name="addbalance", description="💳 Add/Top-up key credits to an existing Reseller")
@app_commands.describe(username="Reseller username", credits="Number of key credits to add")
async def addbalance(interaction: discord.Interaction, username: str, credits: int = 25):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "reseller_username": username.strip(),
        "amount": max(1, credits)
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/addbalance", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="💳 Reseller Balance Updated",
                description=f"Added **+{data['added_amount']} Credits** to Reseller **`@{data['reseller_username']}`**.\n**New Balance:** **`{data['new_balance']} Keys`**",
                color=0x10B981
            )
            embed.set_footer(text="Joyst Auth Enterprise Reseller System")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Failed to update balance')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 9. /redeem (Customer License Key Activation on Discord)
@bot.tree.command(name="redeem", description="🎁 Customers: Redeem your license key to activate software subscription")
@app_commands.describe(key="Your license key (e.g. JOYST-XXXX-XXXX-XXXX)")
async def redeem(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "license_key": key.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/redeem", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🎉 License Key Redeemed Successfully!",
                description=f"Welcome **@{interaction.user.name}**! Your subscription for **`{data['app_name']}`** is now **ACTIVE**.",
                color=0x10B981
            )
            embed.add_field(name="📱 Software", value=f"`{data['app_name']}`", inline=True)
            embed.add_field(name="💎 Rank / Tier", value=f"`{data['rank']}`", inline=True)
            embed.add_field(name="⏳ Expiration", value=f"`{data['expires_at']}`", inline=True)
            embed.add_field(name="🔑 Key Used", value=f"`{key.strip()}`", inline=False)
            embed.set_footer(text="Thank you for your purchase! • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Invalid or already used key')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 10. /genplankey (Generate Developer Plan Upgrade Key)
@bot.tree.command(name="genplankey", description="👑 Owner: Generate VIP / Paid Developer Plan Upgrade Keys")
@app_commands.describe(count="Number of upgrade keys to generate (1-20)", plan="Target Developer Plan (Paid / Enterprise)")
async def genplankey(interaction: discord.Interaction, count: int = 1, plan: str = "Paid"):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "count": min(max(1, count), 20),
        "plan": plan.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genplankey", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            embed = discord.Embed(
                title="👑 Joyst Auth - Developer Plan Keys Generated",
                description=f"Generated **{len(keys)}** Plan Key(s) for **`{data.get('plan', 'Paid')}`** Tier:\n\n" + "\n".join([f"💎 `{k}`" for k in keys]),
                color=0xF59E0B
            )
            embed.add_field(name="👑 Target Plan", value=f"`{data.get('plan', 'Paid')}`", inline=True)
            embed.add_field(name="📦 Features", value="`Unlimited Apps • Unlimited Users • Full Bot Access`", inline=False)
            embed.add_field(name="⚡ How to Redeem", value="Developers can type `/upgrade [key]` or enter it on `joystauth.cc/register`", inline=False)
            embed.set_footer(text="Joyst Auth Enterprise Master License System")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Failed to generate plan keys')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 11. /upgrade (Upgrade Free Developer Account to Paid Plan)
@bot.tree.command(name="upgrade", description="💎 Developers: Upgrade your Joyst Auth account to Paid Plan using a Plan Key")
@app_commands.describe(key="Your Plan Upgrade Key (e.g. JOYST-PAID-XXXX-XXXX-XXXX)")
async def upgrade_cmd(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "plan_key": key.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/upgradeplan", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🎉 Developer Account Upgraded to PAID Plan!",
                description=f"Congratulations **@{data['developer']}**! Your account is now upgraded to **`PAID / ENTERPRISE`**.",
                color=0x10B981
            )
            embed.add_field(name="👤 Developer", value=f"`@{data['developer']}`", inline=True)
            embed.add_field(name="💎 Plan Status", value="`PAID / UNLIMITED`", inline=True)
            embed.add_field(name="📦 Max Applications", value="`Unlimited (999,999)`", inline=True)
            embed.add_field(name="👥 Max Clients", value="`Unlimited (999,999)`", inline=True)
            embed.add_field(name="🤖 Discord Bot", value="🟢 `Full Admin Access Unlocked`", inline=False)
            embed.set_footer(text="Joyst Auth Enterprise • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Invalid or already used key')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 12. /link
@bot.tree.command(name="link", description="🔗 Link your Discord to your Joyst Auth Developer Account (Google / Email)")
@app_commands.describe(email_or_username="Your email address or username registered on joystauth.cc")
async def link_cmd(interaction: discord.Interaction, email_or_username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "email_or_username": email_or_username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/link", json=payload, timeout=15)
        data = res.json()
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title="🔗 Discord Account Linked Successfully!",
                description=f"Your Discord **@{interaction.user.name}** is now permanently linked to **@{data['developer']}** (`{data['plan']}` Plan).",
                color=0x10B981
            )
            embed.add_field(name="Account Email", value=f"`{data['email']}`", inline=True)
            embed.add_field(name="Plan Tier", value=f"`{data['plan']}`", inline=True)
            embed.add_field(name="Bot Access", value="🟢 **Full Admin Permissions Enabled**", inline=False)
            embed.set_footer(text="You can now run /genkey, /stats, /ban, /resethwid from any channel or DM!")
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"❌ **Notice:** {data.get('detail', 'Account not found')}", ephemeral=False)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=False)

# 13. /help
@bot.tree.command(name="help", description="📖 View all available Joyst Auth Discord commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Joyst Auth Enterprise - Discord Slash Commands",
        description="Complete command suite for Software Developers, Resellers & Customers:",
        color=0xE11D48
    )
    embed.add_field(name="👑 `/genplankey [count] [plan]`", value="Generate Paid Developer Plan Upgrade Keys.", inline=False)
    embed.add_field(name="💎 `/upgrade [key]`", value="Upgrade Free Developer account to Paid Plan in 1-click.", inline=False)
    embed.add_field(name="🔗 `/link [email_or_username]`", value="Link your Discord to your Google / Email Joyst account.", inline=False)
    embed.add_field(name="👤 `/adduser [username] [password] [days] [rank]`", value="Create user & password with Dropdown App selector.", inline=False)
    embed.add_field(name="⚡ `/genkey [days] [count] [level]`", value="Generate software license keys with Dropdown App selector.", inline=False)
    embed.add_field(name="💼 `/addreseller [username] [password] [balance]`", value="Create a Reseller account with Key Balance.", inline=False)
    embed.add_field(name="💳 `/addbalance [username] [credits]`", value="Top up key credits for an existing Reseller.", inline=False)
    embed.add_field(name="🔄 `/resethwid [username]`", value="Clear HWID lock for a client to bind a new device.", inline=False)
    embed.add_field(name="🔍 `/userinfo [username]`", value="Inspect subscription expiry, rank, and bound HWID.", inline=False)
    embed.add_field(name="🔨 `/ban` & 🔓 `/unban`", value="Manage client access and security bans.", inline=False)
    embed.add_field(name="📊 `/stats`", value="View live developer summary & telemetry.", inline=False)
    embed.set_footer(text="Joyst Auth Zero-Leak Infrastructure • joystauth.cc")
    await interaction.response.send_message(embed=embed, ephemeral=False)

if __name__ == "__main__":
    if config.get("token") and config["token"] != "YOUR_DISCORD_BOT_TOKEN_HERE":
        bot.run(config["token"])
    else:
        print("[JOYST CORP AUTH BOT] Please configure your Discord bot token in discord_bot/config.json")
