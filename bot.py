import discord
from discord.ext import commands, tasks
from discord import app_commands
import requests
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    cfg = {
        "token": os.environ.get("DISCORD_BOT_TOKEN") or "",
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
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ==================== SERVER CUSTOM ANIMATED EMOJIS ====================
EMOJI = {
    "dot": "<a:black_dot:1535579629253951489>",
    "tick": "<a:CB_greentick:1441097547350282260>",
    "cross": "<a:redtick:1441097679407943782>",
    "bolt": "<a:13969niebieskipiorun:1441085314272722959>",
    "shield": "<a:13969niebieskipiorun:1441085314272722959>",
    "alert": "<a:22593alert:1441088162976895120>",
    "loading": "<a:Green_Loading:1534236460163661976>",
    "bot": "<a:dev:1528079861283946538>",
    "gear": "<a:9093settings:1441087243996496079>",
    "crown": "<a:86751whitedripheart:1320786130869817526>",
    "arrow": "<a:32877animatedarrowbluelite:1396718513787371530>",
    "wave": "<a:pikachu_wave:1320787117881823252>",
    "giveaway": "<a:Giveaway86:1441323391209570446>"
}

# Theme Palette (High-Contrast Cyberpunk Gradient Aesthetics)
COLOR_BRAND = 0xFF2A5F    # Neon Rose / Red Cyberpunk
COLOR_SUCCESS = 0x10B981  # Matrix Emerald
COLOR_WARNING = 0xF59E0B  # Amber Gold
COLOR_DANGER = 0xEF4444   # Crimson Ban
COLOR_PURPLE = 0x8B5CF6   # Electric Violet
COLOR_INFO = 0x38BDF8     # Cyber Sky Blue

STATUS_LIST = [
    ("watching", "🛡️ Joyst Auth Zero-Leak Security"),
    ("watching", "⚡ joystauth.cc • /help"),
    ("competing", "💎 Auth Infrastructure"),
    ("listening", "👑 /genkey • /adduser • /stats")
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

        await bot.change_presence(status=discord.Status.dnd, activity=act)
    except Exception:
        pass

@tasks.loop(minutes=10)
async def auto_sync_commands_loop():
    try:
        await bot.tree.sync()
        print("[JOYST BOT] 🔄 Global slash commands synced seamlessly.")
    except Exception as e:
        print(f"[JOYST SYNC NOTICE] {e}")

@bot.event
async def on_ready():
    print(f"[JOYST BOT] Online as {bot.user.name} (ID: {bot.user.id})")
    act = discord.Activity(type=discord.ActivityType.watching, name="🛡️ Joyst Auth Zero-Leak Security")
    await bot.change_presence(status=discord.Status.dnd, activity=act)
    
    # 1. PURGE ALL GUILD DUPLICATES ON ALL CONNECTED SERVERS
    for guild in bot.guilds:
        try:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
            print(f"[JOYST BOT] 🧹 Cleared duplicate guild commands from: {guild.name}")
        except Exception as e:
            pass

    # 2. SYNC SINGLE CLEAN GLOBAL TREE
    try:
        synced = await bot.tree.sync()
        print(f"[JOYST BOT] ⚡ Successfully synced {len(synced)} unique Global slash commands (Zero Duplicates).")
    except Exception as e:
        print(f"[JOYST BOT] Global sync notice: {e}")

    if not dynamic_presence_loop.is_running():
        dynamic_presence_loop.start()
    if not auto_sync_commands_loop.is_running():
        auto_sync_commands_loop.start()

def parse_api_response(res):
    try:
        return res.json()
    except Exception:
        return {"success": False, "detail": res.text.strip() or f"HTTP Error {res.status_code}"}

def fetch_developer_apps(discord_id: str, discord_username: str):
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/apps", json={
            "discord_id": str(discord_id),
            "discord_username": str(discord_username)
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200:
            return data.get("apps", [])
    except Exception:
        pass
    return []

# ==================== INTERACTIVE SELECT VIEW ====================
class AppSelectView(discord.ui.View):
    def __init__(self, action_type: str, action_data: dict, apps: list):
        super().__init__(timeout=60)
        self.action_type = action_type
        self.action_data = action_data
        self.apps = apps

        options = [
            discord.SelectOption(
                label=app["name"],
                description=f"App ID: #{app['id']} • Version: v{app.get('version', '1.0')}",
                emoji="📦",
                value=app["name"]
            )
            for app in apps[:25]
        ]

        select = discord.ui.Select(
            placeholder="📱 Choose target Application...",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_app = interaction.data["values"][0]
        await interaction.response.defer(ephemeral=False)

        if self.action_type == "genkey":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json=self.action_data, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                keys = data.get("keys", [])
                formatted_keys = "\n".join([f"{EMOJI['dot']} **`{k}`**" for k in keys])
                dur_text = f"**{self.action_data['duration_days']} Days**" if self.action_data['duration_days'] > 0 else f"**Lifetime** {EMOJI['crown']}"
                
                embed = discord.Embed(
                    title=f"{EMOJI['bolt']}  LICENSE KEYS GENERATED",
                    description=(
                        f"### {EMOJI['tick']} Successfully Generated `{len(keys)}` Key(s)\n"
                        f"{EMOJI['arrow']} **Application:** `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Duration:** {dur_text}\n"
                        f"{EMOJI['arrow']} **Rank Tier:** `{self.action_data['level']}`\n\n"
                        f"**━━━━━━━━━ KEYS VAULT ━━━━━━━━━**\n"
                        f"{formatted_keys}\n"
                        f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**"
                    ),
                    color=COLOR_BRAND
                )
                embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title=f"{EMOJI['cross']}  KEY GENERATION FAILED",
                    description=f"> {EMOJI['alert']} **Reason:** `{data.get('detail', 'Failed to generate keys.')}`",
                    color=COLOR_DANGER
                )
                await interaction.edit_original_response(content=None, embed=embed, view=None)

        elif self.action_type == "adduser":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/adduser", json=self.action_data, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                embed = discord.Embed(
                    title=f"{EMOJI['bot']}  CLIENT ACCOUNT CREATED",
                    description=(
                        f"### {EMOJI['tick']} User `{data['username']}` is Now Active!\n"
                        f"{EMOJI['arrow']} **Username:** `{data['username']}`\n"
                        f"{EMOJI['arrow']} **Password:** `{self.action_data['password']}`\n"
                        f"{EMOJI['arrow']} **Application:** `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Subscription:** `{data['subscription']}`\n"
                        f"{EMOJI['arrow']} **Expiry Date:** `{data['expires_at']}`\n"
                        f"{EMOJI['arrow']} **HWID Binding:** `Ready on 1st Login` {EMOJI['shield']}"
                    ),
                    color=COLOR_SUCCESS
                )
                embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title=f"{EMOJI['cross']}  USER CREATION FAILED",
                    description=f"> {EMOJI['alert']} **Reason:** `{data.get('detail', 'Failed to create user.')}`",
                    color=COLOR_DANGER
                )
                await interaction.edit_original_response(content=None, embed=embed, view=None)

        elif self.action_type == "maintenance":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/maintenance", json=self.action_data, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                is_maint = data.get("is_maintenance", False)
                embed = discord.Embed(
                    title=f"{'🚨' if is_maint else '🟢'}  APPLICATION MAINTENANCE MODE UPDATED",
                    description=(
                        f"### Status: **{data.get('status_label', 'UPDATED')}**\n"
                        f"{EMOJI['arrow']} **Application:** `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Client Action:** `{'FORCE-BLOCKING ALL EXEs' if is_maint else 'ALLOWING ALL LOGINS'}`\n"
                        f"{EMOJI['arrow']} **Notice:** `{data.get('maintenance_message', 'No custom message')}`\n"
                    ),
                    color=COLOR_DANGER if is_maint else COLOR_SUCCESS
                )
                embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title=f"{EMOJI['cross']}  MAINTENANCE TOGGLE FAILED",
                    description=f"> {EMOJI['alert']} **Reason:** `{data.get('detail', 'Failed to update maintenance mode.')}`",
                    color=COLOR_DANGER
                )
                await interaction.edit_original_response(content=None, embed=embed, view=None)

        elif self.action_type == "warning":
            self.action_data["app_name"] = selected_app
            res = requests.post(f"{config['api_url']}/api/v1/admin/bot/warning", json=self.action_data, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                embed = discord.Embed(
                    title=f"🚨  LIVE EMERGENCY WARNING BROADCASTED",
                    description=(
                        f"### {EMOJI['tick']} Warning Sent to All Running and New Clients!\n"
                        f"{EMOJI['arrow']} **Target App:** `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Title:** `{self.action_data.get('title')}`\n"
                        f"{EMOJI['arrow']} **Notice Body:** `{self.action_data.get('message')}`\n"
                        f"{EMOJI['arrow']} **Delivery:** `Instant In-App Pop-up on next poll / login`"
                    ),
                    color=COLOR_WARNING if self.action_data.get('type') == 'warning' else COLOR_DANGER
                )
                embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(content=None, embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title=f"{EMOJI['cross']}  BROADCAST FAILED",
                    description=f"> {EMOJI['alert']} **Reason:** `{data.get('detail', 'Failed to broadcast warning.')}`",
                    color=COLOR_DANGER
                )
                await interaction.edit_original_response(content=None, embed=embed, view=None)

# ==================== SLASH COMMANDS ====================


# 0. /ping
@bot.tree.command(name="ping", description="🏓 Check live Discord bot latency & cloud telemetry")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def ping_cmd(interaction: discord.Interaction):
    import time
    start_time = time.perf_counter()
    await interaction.response.defer(ephemeral=False)
    end_time = time.perf_counter()

    rest_latency = round((end_time - start_time) * 1000, 2)
    ws_latency = round(bot.latency * 1000, 2) if bot.latency and bot.latency > 0 else 1.0

    embed = discord.Embed(
        title=f"{EMOJI['bolt']}  JOYST AUTH • NODE TELEMETRY",
        description=(
            f"### {EMOJI['tick']} System Status: **OPERATIONAL (0-DELAY)**\n"
            f"{EMOJI['arrow']} **Gateway Ping:** `{ws_latency} ms` {EMOJI['dot']}\n"
            f"{EMOJI['arrow']} **REST Round-Trip:** `{rest_latency} ms` {EMOJI['dot']}\n"
            f"{EMOJI['arrow']} **Security Shield:** `Active • Zero-Leak` {EMOJI['shield']}\n"
            f"{EMOJI['arrow']} **Edge Portal:** [joystauth.cc](https://joystauth.cc)"
        ),
        color=COLOR_SUCCESS if ws_latency < 120 else COLOR_WARNING,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url="https://joystauth.cc/static/img/joyst_logo.png")
    embed.set_footer(text="Joyst Corporation • High-Speed Node Enclave", icon_url=interaction.user.display_avatar.url)
    await interaction.followup.send(embed=embed)

# 1. /help
@bot.tree.command(name="help", description="📖 View all available Joyst Auth slash commands")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI['bolt']}  JOYST AUTH • COMMAND SUITE",
        description=(
            f"**Zero-Leak Security & Licensing Engine** {EMOJI['shield']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"### {EMOJI['crown']} **Developer & Admin Commands**\n"
            f"{EMOJI['arrow']} **`/link [email_or_user]`**\n"
            f"┗ `Link Discord ID to Joyst Account in 1-Click`\n\n"
            f"{EMOJI['arrow']} **`/genkey [days] [count] [rank]`**\n"
            f"┗ `Generate License Keys with App Dropdown`\n\n"
            f"{EMOJI['arrow']} **`/adduser [user] [pass] [days]`**\n"
            f"┗ `Create Client Account with App Dropdown`\n\n"
            f"{EMOJI['arrow']} **`/genplankey [count] [plan]`**\n"
            f"┗ `Generate Paid Plan VIP Upgrade Keys`\n\n"
            f"{EMOJI['arrow']} **`/upgrade [plan_key]`**\n"
            f"┗ `Instant Upgrade Free Account to Paid Plan`\n\n"
            f"### {EMOJI['gear']} **Client & Security Management**\n"
            f"{EMOJI['arrow']} **`/resethwid [username]`**\n"
            f"┗ `Reset HWID lock for a client to bind new PC`\n\n"
            f"{EMOJI['arrow']} **`/userinfo [username]`**\n"
            f"┗ `Inspect client expiry, rank, and bound HWID`\n\n"
            f"{EMOJI['arrow']} **`/ban [user]` • `/unban [user]`**\n"
            f"┗ `Manage client security bans and permissions`\n\n"
            f"### {EMOJI['giveaway']} **Reseller & Telemetry Suite**\n"
            f"{EMOJI['arrow']} **`/addreseller [user] [pass] [balance]`**\n"
            f"┗ `Create Reseller account with Key Balance`\n\n"
            f"{EMOJI['arrow']} **`/addbalance [user] [credits]`**\n"
            f"┗ `Top up credits for an existing Reseller`\n\n"
            f"{EMOJI['arrow']} **`/stats`**\n"
            f"┗ `Live Developer Telemetry & Analytics`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=COLOR_BRAND
    )
    embed.set_footer(text="Joyst Auth • joystauth.cc", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, ephemeral=False)

# 2. /link
@bot.tree.command(name="link", description="🔗 Link your Discord to your Joyst Auth Developer Account")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
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
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['tick']}  ACCOUNT LINKED SUCCESSFULLY",
                description=(
                    f"### {EMOJI['wave']} Welcome **@{interaction.user.name}**!\n\n"
                    f"{EMOJI['arrow']} **Developer:** `@{data['developer']}`\n"
                    f"{EMOJI['arrow']} **Email / ID:** `{data.get('email', 'Google Account')}`\n"
                    f"{EMOJI['arrow']} **Plan Status:** `{data['plan']} Tier` {EMOJI['crown']}\n"
                    f"{EMOJI['arrow']} **Bot Controller:** `Authorized` {EMOJI['shield']}\n\n"
                    f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                    f"{EMOJI['dot']} You can now run `/genkey`, `/adduser`, `/stats` directly!"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  LINKING FAILED",
                description=(
                    f"> {EMOJI['alert']} **Error:** `{data.get('detail', 'Account not found.')}`\n\n"
                    f"**Troubleshooting:**\n"
                    f"{EMOJI['dot']} Make sure you entered your correct email or username.\n"
                    f"{EMOJI['dot']} Register on `https://joystauth.cc/register` if you haven't yet."
                ),
                color=COLOR_WARNING
            )
            embed.set_footer(text="Joyst Auth • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 3. /genkey
@bot.tree.command(name="genkey", description="⚡ Generate license keys for your application")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    days="Duration in days (-1 for lifetime)",
    count="Number of keys to generate (1-50)",
    level="Subscription Rank (e.g. default, VIP)",
    app="Application Name (leave empty for Dropdown selector)"
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

    if not app:
        apps = fetch_developer_apps(str(interaction.user.id), str(interaction.user.name))
        if len(apps) > 1:
            view = AppSelectView("genkey", payload, apps)
            await interaction.followup.send(f"{EMOJI['bolt']} **Select target Application from dropdown below:**", view=view)
            return

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            app_name = data.get("app_name", "JOYST")
            formatted_keys = "\n".join([f"{EMOJI['dot']} **`{k}`**" for k in keys])
            dur_text = f"**{days} Days**" if days > 0 else f"**Lifetime** {EMOJI['crown']}"

            embed = discord.Embed(
                title=f"{EMOJI['bolt']}  LICENSE KEYS GENERATED",
                description=(
                    f"### {EMOJI['tick']} Generated `{len(keys)}` Key(s) for `{app_name}`\n"
                    f"{EMOJI['arrow']} **Application:** `{app_name}`\n"
                    f"{EMOJI['arrow']} **Duration:** {dur_text}\n"
                    f"{EMOJI['arrow']} **Rank Tier:** `{level}`\n"
                    f"{EMOJI['arrow']} **Developer:** `@{data.get('developer', interaction.user.name)}`\n\n"
                    f"**━━━━━━━━━ KEYS VAULT ━━━━━━━━━**\n"
                    f"{formatted_keys}\n"
                    f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**"
                ),
                color=COLOR_BRAND
            )
            embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  KEY GENERATION NOTICE",
                description=f"> {EMOJI['alert']} **Detail:** `{data.get('detail', 'Key generation failed.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 4. /adduser
@bot.tree.command(name="adduser", description="👤 Create client username and password directly")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(
    username="Client username",
    password="Client password",
    days="Subscription duration in days (-1 for lifetime)",
    rank="Subscription Rank (e.g. default, VIP)",
    app="Application Name (leave empty for Dropdown selector)"
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

    if not app:
        apps = fetch_developer_apps(str(interaction.user.id), str(interaction.user.name))
        if len(apps) > 1:
            view = AppSelectView("adduser", payload, apps)
            await interaction.followup.send(f"{EMOJI['bot']} **Select target Application from dropdown below:**", view=view)
            return

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/adduser", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['bot']}  CLIENT ACCOUNT CREATED",
                description=(
                    f"### {EMOJI['tick']} User `{data['username']}` Created for `{data['app_name']}`\n\n"
                    f"{EMOJI['arrow']} **Username:** `{data['username']}`\n"
                    f"{EMOJI['arrow']} **Password:** `{password}`\n"
                    f"{EMOJI['arrow']} **Application:** `{data['app_name']}`\n"
                    f"{EMOJI['arrow']} **Subscription:** `{data['subscription']}`\n"
                    f"{EMOJI['arrow']} **Expires:** `{data['expires_at']}`\n"
                    f"{EMOJI['arrow']} **HWID Binding:** `Ready on 1st Login` {EMOJI['shield']}"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth • Zero-Leak Security", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  USER CREATION NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to create user.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 5. /genplankey
@bot.tree.command(name="genplankey", description="👑 Owner: Generate Paid Developer Plan Upgrade Keys")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(count="Number of keys to generate (1-20)", plan="Target Developer Plan (Paid /)")
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
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            formatted_keys = "\n".join([f"{EMOJI['dot']} **`{k}`**" for k in keys])
            embed = discord.Embed(
                title=f"{EMOJI['crown']}  DEVELOPER PLAN UPGRADE KEYS",
                description=(
                    f"### {EMOJI['tick']} Generated `{len(keys)}` Plan Key(s) for `{data.get('plan', 'Paid')}` Tier\n\n"
                    f"{EMOJI['arrow']} **Target Plan:** `{data.get('plan', 'Paid')}`\n"
                    f"{EMOJI['arrow']} **Features:** `Unlimited Apps • Unlimited Users • Full Bot Access`\n\n"
                    f"**━━━━━━━━━ UPGRADE KEYS ━━━━━━━━━**\n"
                    f"{formatted_keys}\n"
                    f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                    f"{EMOJI['arrow']} **How to Redeem:** `/upgrade [key]` or enter on website."
                ),
                color=COLOR_WARNING
            )
            embed.set_footer(text="Joyst Auth Master License System", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to generate plan keys.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 6. /upgrade
@bot.tree.command(name="upgrade", description="💎 Upgrade your Developer account to Paid Plan using a Key")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(key="Your Plan Upgrade Key")
async def upgrade_cmd(interaction: discord.Interaction, key: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "plan_key": key.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/upgradeplan", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['crown']}  ACCOUNT UPGRADED TO PAID TIER",
                description=(
                    f"### {EMOJI['wave']} Congratulations **@{data['developer']}**!\n\n"
                    f"{EMOJI['arrow']} **Developer:** `@{data['developer']}`\n"
                    f"{EMOJI['arrow']} **Plan Status:** `PAID / UNLIMITED` {EMOJI['crown']}\n"
                    f"{EMOJI['arrow']} **Max Applications:** `Unlimited (999,999)`\n"
                    f"{EMOJI['arrow']} **Max Clients:** `Unlimited (999,999)`\n"
                    f"{EMOJI['arrow']} **Discord Bot:** `Full Admin Unlocked` {EMOJI['shield']}"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  UPGRADE FAILED",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Invalid or already used Upgrade Key.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 7. /resethwid
@bot.tree.command(name="resethwid", description="🔄 Clear HWID lock for a client")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="Client username to reset")
async def resethwid(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/resethwid", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['gear']}  HWID RESET COMPLETED",
                description=(
                    f"### {EMOJI['tick']} HWID lock for `{data['username']}` has been cleared!\n\n"
                    f"{EMOJI['arrow']} **Client:** `{data['username']}`\n"
                    f"{EMOJI['arrow']} **Binding Status:** `Ready for New Machine` {EMOJI['shield']}\n"
                    f"{EMOJI['dot']} Client will automatically lock to their next login device."
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth Security • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'User not found in your applications.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 8. /userinfo
@bot.tree.command(name="userinfo", description="🔍 Look up a registered client'sfile, subscription & HWID")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="Username to inspect")
async def userinfo(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/userinfo", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            u = data["user"]
            status_text = f"**BANNED** {EMOJI['cross']}" if u["is_banned"] else f"**ACTIVE** {EMOJI['tick']}"
            embed = discord.Embed(
                title=f"{EMOJI['bot']}  CLIENTFILE: {u['username']}",
                description=(
                    f"{EMOJI['arrow']} **Application:** `{u['app_name']}`\n"
                    f"{EMOJI['arrow']} **Status:** {status_text}\n"
                    f"{EMOJI['arrow']} **Subscription:** `{u['subscription']}` (Lv.{u['level']})\n"
                    f"{EMOJI['arrow']} **Expires:** `{u['expires_at']}`\n"
                    f"{EMOJI['arrow']} **Last Login IP:** `{u['last_ip']}`\n"
                    f"{EMOJI['arrow']} **Bound HWID:** `{u['hwid'][:24]}...`" if len(u['hwid']) > 24 else f"{EMOJI['arrow']} **Bound HWID:** `{u['hwid']}`"
                ),
                color=COLOR_DANGER if u["is_banned"] else COLOR_SUCCESS
            )
            if u["is_banned"]:
                embed.add_field(name=f"{EMOJI['alert']} Ban Reason", value=f"`{u['ban_reason']}`", inline=False)
            embed.set_footer(text="Joyst Auth Database • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'User not found.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 9. /ban & /unban
@bot.tree.command(name="ban", description="🔨 Ban a client user from authenticating")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="User to ban", reason="Reason for ban")
async def ban(interaction: discord.Interaction, username: str, reason: str = "Banned by Admin"):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip(),
        "reason": reason.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/ban", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  USER ACCOUNT BANNED",
                description=(
                    f"### {EMOJI['alert']} User `{data['username']}` Has Been Permanently Banned\n\n"
                    f"{EMOJI['arrow']} **Client:** `{data['username']}`\n"
                    f"{EMOJI['arrow']} **Reason:** `{data['reason']}`\n"
                    f"{EMOJI['dot']} All authentication attempts for this user will be rejected."
                ),
                color=COLOR_DANGER
            )
            embed.set_footer(text="Joyst Auth Shield • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to ban user.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

@bot.tree.command(name="unban", description="🔓 Unban a previously banned client user")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="User to unban")
async def unban(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "target_username": username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/unban", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['tick']}  USER UNBANNED",
                description=(
                    f"### {EMOJI['wave']} User `{data['username']}` Access Restored\n\n"
                    f"{EMOJI['arrow']} **Client:** `{data['username']}`\n"
                    f"{EMOJI['arrow']} **Status:** `Authorized to Login` {EMOJI['shield']}"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth Shield • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to unban user.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 10. /stats
@bot.tree.command(name="stats", description="📊 View live statistics of your applications, users, and licenses")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name)
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/stats", json=payload, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['loading']}  JOYST AUTH • DEVELOPER TELEMETRY",
                description=(
                    f"**Live Overview for Developer `@{data['developer']}`** (`{data['plan']}` Tier {EMOJI['crown']})\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"{EMOJI['arrow']} **Total Applications:** ` {data['total_apps']} ` ({', '.join(data['apps_list']) or 'None'})\n"
                    f"{EMOJI['arrow']} **Total Registered Clients:** ` {data['total_users']} `\n"
                    f"{EMOJI['arrow']} **Total License Keys:** ` {data['total_keys']} `\n"
                    f"{EMOJI['arrow']} **Available (Unused) Keys:** ` {data['unused_keys']} ` {EMOJI['tick']}\n"
                    f"{EMOJI['arrow']} **Permanently Banned Users:** ` {data['banned_users']} ` {EMOJI['cross']}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                ),
                color=COLOR_INFO
            )
            embed.set_footer(text="Joyst Auth Zero-Leak Infrastructure • joystauth.cc", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to fetch telemetry.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

# 11. /addreseller & /addbalance
@bot.tree.command(name="addreseller", description="💼 Create a new Reseller with key credits balance")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="Reseller username", password="Password", balance="Initial Credits")
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
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['giveaway']}  RESELLER ACCOUNT CREATED",
                description=(
                    f"### {EMOJI['tick']} Reseller `@{data['reseller_username']}` is Active!\n\n"
                    f"{EMOJI['arrow']} **Reseller Username:** `@{data['reseller_username']}`\n"
                    f"{EMOJI['arrow']} **Initial Password:** `{password}`\n"
                    f"{EMOJI['arrow']} **Allotted Balance:** `{data['balance']} Key Credits`\n"
                    f"{EMOJI['arrow']} **Reseller Portal:** `https://joystauth.cc/reseller/login`"
                ),
                color=COLOR_PURPLE
            )
            embed.set_footer(text="Joyst Auth Reseller System", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to create reseller.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

@bot.tree.command(name="addbalance", description="💳 Top up key credits for an existing Reseller")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(username="Reseller username", credits="Credits to add")
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
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['tick']}  RESELLER BALANCE UPDATED",
                description=(
                    f"### {EMOJI['giveaway']} Added **+{data['added_amount']} Credits** to `@{data['reseller_username']}`\n\n"
                    f"{EMOJI['arrow']} **Reseller:** `@{data['reseller_username']}`\n"
                    f"{EMOJI['arrow']} **Added Amount:** `+{data['added_amount']} Keys`\n"
                    f"{EMOJI['arrow']} **New Total Balance:** `{data['new_balance']} Keys` {EMOJI['crown']}"
                ),
                color=COLOR_SUCCESS
            )
            embed.set_footer(text="Joyst Auth Reseller System", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  NOTICE",
                description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to update balance.')}`",
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
    except Exception as e:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  CONNECTION ERROR",
            description=f"> {EMOJI['alert']} `{str(e)}`",
            color=COLOR_DANGER
        )
        await interaction.followup.send(embed=embed, ephemeral=False)

@bot.tree.command(name="maintenance", description="⏸️ Toggle Maintenance Mode for your App (Force-Blocks all EXEs)")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(state="Maintenance state", message="Optional custom maintenance notice")
@app_commands.choices(state=[
    app_commands.Choice(name="🚨 Activate Maintenance (Block all EXEs)", value="enable"),
    app_commands.Choice(name="🟢 Resume Online (Allow EXEs)", value="disable"),
    app_commands.Choice(name="🔄 Toggle State", value="toggle")
])
async def maintenance_cmd(interaction: discord.Interaction, state: str = "toggle", message: str = ""):
    apps = fetch_developer_apps(interaction.user.id)
    if not apps:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  NO LINKED ACCOUNT FOUND",
            description=f"> {EMOJI['alert']} Please run **`/link [email_or_username]`** first to connect your Joyst account.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    action_data = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "state": state,
        "message": message.strip() if message else None
    }

    view = AppSelectView(apps, "maintenance", action_data)
    await interaction.response.send_message("⚙️ **Select which Application to toggle Maintenance Mode:**", view=view, ephemeral=False)

@bot.tree.command(name="warning", description="🚨 Broadcast an Emergency Warning / Notice to all .exe client screens")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.describe(title="Warning Title / Heading", message="Notice text to show in client pop-up", severity="Severity level")
@app_commands.choices(severity=[
    app_commands.Choice(name="🚨 Critical / Ban Wave Alert (Red)", value="danger"),
    app_commands.Choice(name="⚠️ Maintenance / Patch Warning (Orange)", value="warning"),
    app_commands.Choice(name="ℹ️ Info Notice (Blue)", value="info"),
    app_commands.Choice(name="🟢 Status Update (Green)", value="success")
])
async def warning_cmd(interaction: discord.Interaction, title: str, message: str, severity: str = "danger"):
    apps = fetch_developer_apps(interaction.user.id)
    if not apps:
        embed = discord.Embed(
            title=f"{EMOJI['cross']}  NO LINKED ACCOUNT FOUND",
            description=f"> {EMOJI['alert']} Please run **`/link [email_or_username]`** first to connect your Joyst account.",
            color=COLOR_WARNING
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    action_data = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "title": title.strip(),
        "message": message.strip(),
        "type": severity
    }

    view = AppSelectView(apps, "warning", action_data)
    await interaction.response.send_message("📢 **Select which Application to Broadcast this Warning to:**", view=view, ephemeral=False)

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN") or config.get("token")
    bot.run("")

def run_discord_bot():
    token = os.environ.get('DISCORD_BOT_TOKEN') or config.get('token')
    if token and token != 'YOUR_DISCORD_BOT_TOKEN_HERE':
        bot.run(token)
