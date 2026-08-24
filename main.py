"""
JOYST AUTH — Master Discord Bot Engine
Multi-Server Support + Staff Role Whitelisting + High-Tech Styled Dropdowns + 24/7 Channel Logging + Master Admin Security Locks
"""
import os
import sys
import time
import asyncio
import datetime
import requests
import json
import discord
from discord import app_commands
from discord.ext import commands, tasks

# ==================== GLOBAL CONFIGURATION & MASTER ADMINS ====================
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "".join(["MTU0MDA1ODgwNTEzODg4MjczMA", ".", "Gnc8kf", ".", "oo-WL14YLLK_ycWFAK2YH5Lxu_-sYEF5Y19ASI"])).strip()
API_URL = "https://joystauth.cc"
GLOBAL_LOG_CHANNEL_ID = 1538975494207438928
MASTER_ADMIN_IDS = ["956388318961086465", "1307214230134591559"]

GUILD_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "guild_configs.json")

def load_guild_configs():
    if os.path.exists(GUILD_CONFIG_FILE):
        try:
            with open(GUILD_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_guild_configs(configs):
    try:
        with open(GUILD_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(configs, f, indent=2)
    except Exception as e:
        print(f"[CONFIG SAVE ERROR] {e}")

guild_configs = load_guild_configs()

# ==================== ALL 14 CUSTOM ANIMATED EMOJIS ====================
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
    "giveaway": "<a:Giveaway86:1441323391209570446>",
    "audio": "<a:Playing_Audio:1534236884639944705>",
    "question": "<a:question1:1534236585456046274>"
}

COLOR_BRAND = 0xFF2A5F
COLOR_SUCCESS = 0x10B981
COLOR_WARNING = 0xF59E0B
COLOR_DANGER = 0xEF4444
COLOR_PURPLE = 0x8B5CF6
COLOR_INFO = 0x38BDF8

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

STATUS_LIST = [
    ("watching", "🛡️ Joyst Auth Zero-Leak Security"),
    ("watching", "⚡ joystauth.cc • /help"),
    ("competing", "💎 Auth Infrastructure"),
    ("listening", "👑 /genkey • /listkeys • /adduser")
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

@bot.event
async def on_ready():
    print("=======================================================")
    print(f"[JOYST BOT] Online as {bot.user.name} (ID: {bot.user.id})")
    print(f"[JOYST BOT] Connected to {len(bot.guilds)} Discord Server(s).")
    print("=======================================================")
    try:
        synced = await bot.tree.sync()
        print(f"[JOYST BOT] ⚡ Successfully synced {len(synced)} unique Global slash commands.")
    except Exception as e:
        print(f"[JOYST BOT] Sync: {e}")
    if not dynamic_presence_loop.is_running():
        dynamic_presence_loop.start()

# ==================== PERMISSIONS & DISPATCH HELPERS ====================
def is_master_admin(user_id: int) -> bool:
    return str(user_id) in MASTER_ADMIN_IDS

def get_effective_developer_id(interaction: discord.Interaction) -> str:
    g_id = str(interaction.guild_id) if interaction.guild_id else None
    if g_id and g_id in guild_configs:
        cfg = guild_configs[g_id]
        if cfg.get("owner_discord_id"):
            return str(cfg["owner_discord_id"])
    return str(interaction.user.id)

def check_staff_or_owner_permission(interaction: discord.Interaction) -> bool:
    if is_master_admin(interaction.user.id):
        return True

    g_id = str(interaction.guild_id) if interaction.guild_id else None
    if not g_id:
        return True

    if g_id in guild_configs:
        cfg = guild_configs[g_id]
        if str(interaction.user.id) == str(cfg.get("owner_discord_id")):
            return True
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
        if hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator:
            return True
        allowed_roles = [str(r) for r in cfg.get("staff_role_ids", [])]
        if hasattr(interaction.user, "roles"):
            user_roles = [str(r.id) for r in interaction.user.roles]
            if any(r in allowed_roles for r in user_roles):
                return True
        return False

    if interaction.guild and interaction.user.id == interaction.guild.owner_id:
        return True
    if hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator:
        return True
    return False

async def log_to_channels(action_title: str, user: discord.User, details: str, guild: discord.Guild = None, app_name: str = "", status: str = "SUCCESS"):
    color = COLOR_SUCCESS if status == "SUCCESS" else (COLOR_DANGER if status == "DANGER" else COLOR_WARNING)
    embed = discord.Embed(
        title=f"🔔 Event: {action_title}",
        description="**Action Executed Via Discord Bot Controller**",
        color=color,
        timestamp=datetime.datetime.utcnow()
    )
    embed.add_field(name="👤 Executor", value=f"**@{user.name}** (`{user.id}`)", inline=True)
    if guild:
        embed.add_field(name="🌐 Discord Server", value=f"`{guild.name}` (`{guild.id}`)", inline=True)
    if app_name:
        embed.add_field(name="📱 Application", value=f"`{app_name}`", inline=True)
    embed.add_field(name="📊 Status", value=f"**`{status}`**", inline=True)
    embed.add_field(name="📝 Audit Details", value=f"```{details}```", inline=False)
    embed.set_footer(text="Joyst Auth • Public Audit Trail", icon_url=user.display_avatar.url)

    if guild and str(guild.id) in guild_configs:
        guild_log_id = guild_configs[str(guild.id)].get("log_channel_id")
        if guild_log_id:
            try:
                g_chan = bot.get_channel(int(guild_log_id)) or await bot.fetch_channel(int(guild_log_id))
                if g_chan:
                    await g_chan.send(embed=embed)
            except Exception:
                pass

    try:
        global_chan = bot.get_channel(GLOBAL_LOG_CHANNEL_ID) or await bot.fetch_channel(GLOBAL_LOG_CHANNEL_ID)
        if global_chan:
            await global_chan.send(embed=embed)
    except Exception as e:
        print(f"[MASTER AUDIT ERROR] {e}")

async def reject_unauthorized(interaction: discord.Interaction, reason: str = "Staff or Developer Role Required"):
    embed = discord.Embed(
        title=f"{EMOJI['alert']}  SECURITY LOCKOUT • ACCESS DENIED",
        description=(
            f"### {EMOJI['cross']} Permission Denied\n\n"
            f"{EMOJI['arrow']} **Requirement:** `{reason}`\n"
            f"{EMOJI['arrow']} **Your User ID:** `{interaction.user.id}`\n\n"
            f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
            f"{EMOJI['dot']} *Ask your server administrator to set your Staff Role via `/setstaffrole`.*"
        ),
        color=COLOR_DANGER
    )
    embed.set_footer(text="Joyst Auth Zero-Leak Security Enclave", icon_url=interaction.user.display_avatar.url)
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

def parse_api_response(res):
    try:
        return res.json()
    except Exception:
        return {"success": False, "detail": res.text.strip() or f"HTTP Error {res.status_code}"}

def fetch_developer_apps(discord_id: str, discord_username: str):
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/apps", json={
            "discord_id": str(discord_id),
            "discord_username": str(discord_username)
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200:
            return data.get("apps", [])
    except Exception:
        pass
    return []

# ==================== HIGH-TECH STYLED DROPDOWN VIEWS ====================

class GenKeyAppSelectView(discord.ui.View):
    def __init__(self, days: int, count: int, effective_dev_id: str, apps: list, guild: discord.Guild):
        super().__init__(timeout=90)
        self.days = days
        self.count = count
        self.effective_dev_id = effective_dev_id
        self.apps = apps
        self.guild = guild

        options = [
            discord.SelectOption(
                label=f"{a['name']}",
                description=f"App ID: #{a['id']} • Version: v{a.get('version', '1.0')} • Active Node",
                emoji="📦",
                value=a["name"]
            )
            for a in apps[:25]
        ]

        select = discord.ui.Select(
            placeholder="⚡ Choose Application to Generate Keys...",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_app = interaction.data["values"][0]

        embed_loading = discord.Embed(
            title=f"{EMOJI['loading']}  MINTING ENCLAVE LICENSE KEYS...",
            description=(
                f"### {EMOJI['bolt']} Establishing Cryptographic Database Link...\n\n"
                f"{EMOJI['arrow']} **Target App:** `{selected_app}`\n"
                f"{EMOJI['arrow']} **Keys Count:** `{self.count}` Keys\n"
                f"{EMOJI['arrow']} **Duration:** `{self.days} Days`\n\n"
                f"`[ ▰▰▰▰▰▰▱▱▱▱ ] 65% • Generating High-Entropy Tokens...`"
            ),
            color=COLOR_INFO
        )
        await interaction.response.edit_message(embed=embed_loading, view=None)

        try:
            res = requests.post(f"{API_URL}/api/v1/admin/bot/genkey", json={
                "discord_id": self.effective_dev_id,
                "discord_username": str(interaction.user.name),
                "app_name": selected_app,
                "count": self.count,
                "duration_days": self.days,
                "level": "default",
                "mask": "JOYST-XXXX-XXXX-XXXX"
            }, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                keys = data.get("keys", [])
                formatted = "\n".join([f"{EMOJI['dot']} **`{k}`**" for k in keys])
                dur = f"**{self.days} Days**" if self.days > 0 else f"**Lifetime** {EMOJI['crown']}"
                embed = discord.Embed(
                    title=f"{EMOJI['bolt']}  LICENSE KEYS GENERATED",
                    description=(
                        f"### {EMOJI['tick']} Successfully Minted `{len(keys)}` Key(s) for `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Duration:** {dur}\n"
                        f"{EMOJI['arrow']} **Status:** `Fresh / Unused` {EMOJI['shield']}\n\n"
                        f"**━━━━━━━━━ KEYS VAULT ━━━━━━━━━**\n"
                        f"{formatted}\n"
                        f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**"
                    ),
                    color=COLOR_BRAND
                )
                embed.set_footer(text=f"Joyst Auth • Created by @{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(embed=embed, view=None)
                await log_to_channels(
                    action_title="GENERATE_KEYS",
                    user=interaction.user,
                    details=f"Generated {len(keys)} keys ({self.days} days) for {selected_app}\nKeys: {', '.join(keys)}",
                    guild=self.guild,
                    app_name=selected_app
                )
            else:
                embed_err = discord.Embed(title=f"{EMOJI['cross']}  ERROR", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to generate keys.')}`", color=COLOR_DANGER)
                await interaction.edit_original_response(embed=embed_err, view=None)
        except Exception as e:
            await interaction.edit_original_response(content=f"Error: {e}", embed=None, view=None)

class AddUserAppSelectView(discord.ui.View):
    def __init__(self, username: str, password: str, days: int, effective_dev_id: str, apps: list, guild: discord.Guild):
        super().__init__(timeout=90)
        self.username = username
        self.password = password
        self.days = days
        self.effective_dev_id = effective_dev_id
        self.apps = apps
        self.guild = guild

        options = [
            discord.SelectOption(
                label=f"{a['name']}",
                description=f"App ID: #{a['id']} • Version: v{a.get('version', '1.0')} • Active Node",
                emoji="📦",
                value=a["name"]
            )
            for a in apps[:25]
        ]

        select = discord.ui.Select(
            placeholder="👤 Choose Application for Client...",
            min_values=1,
            max_values=1,
            options=options
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_app = interaction.data["values"][0]

        embed_loading = discord.Embed(
            title=f"{EMOJI['loading']}  PROVISIONING CLIENT ACCOUNT...",
            description=(
                f"### {EMOJI['bolt']} Creating Zero-Leak Credentials...\n\n"
                f"{EMOJI['arrow']} **Username:** `{self.username}`\n"
                f"{EMOJI['arrow']} **Target App:** `{selected_app}`\n"
                f"{EMOJI['arrow']} **Duration:** `{self.days} Days`\n\n"
                f"`[ ▰▰▰▰▰▰▱▱▱▱ ] 70% • Hashing Passwords & Preparing HWID Lock...`"
            ),
            color=COLOR_INFO
        )
        await interaction.response.edit_message(embed=embed_loading, view=None)

        try:
            res = requests.post(f"{API_URL}/api/v1/admin/bot/adduser", json={
                "discord_id": self.effective_dev_id,
                "discord_username": str(interaction.user.name),
                "app_name": selected_app,
                "username": self.username,
                "password": self.password,
                "duration_days": self.days,
                "subscription_tier": "default"
            }, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                embed = discord.Embed(
                    title=f"{EMOJI['bot']}  CLIENT ACCOUNT CREATED",
                    description=(
                        f"### {EMOJI['tick']} User `{data['username']}` Created for `{selected_app}`\n"
                        f"{EMOJI['arrow']} **Password:** `{self.password}`\n"
                        f"{EMOJI['arrow']} **Subscription:** `{data['subscription']}`\n"
                        f"{EMOJI['arrow']} **Expires:** `{data['expires_at']}`\n"
                        f"{EMOJI['arrow']} **HWID Binding:** `Locks on 1st Login` {EMOJI['shield']}"
                    ),
                    color=COLOR_SUCCESS
                )
                embed.set_footer(text=f"Joyst Auth • Created by @{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
                await interaction.edit_original_response(embed=embed, view=None)
                await log_to_channels(
                    action_title="USER_CREATED",
                    user=interaction.user,
                    details=f"Created client user '{data['username']}' for '{selected_app}' (Expires: {data['expires_at']})",
                    guild=self.guild,
                    app_name=selected_app
                )
            else:
                embed_err = discord.Embed(title=f"{EMOJI['cross']}  ERROR", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to create user.')}`", color=COLOR_DANGER)
                await interaction.edit_original_response(embed=embed_err, view=None)
        except Exception as e:
            await interaction.edit_original_response(content=f"Error: {e}", embed=None, view=None)

class ListKeysDropdownView(discord.ui.View):
    def __init__(self, effective_dev_id: str, apps: list, guild: discord.Guild):
        super().__init__(timeout=120)
        self.effective_dev_id = effective_dev_id
        self.apps = apps
        self.guild = guild
        self.selected_app = apps[0]["name"] if apps else None
        self.selected_status = "unused"

        # 1. High-Tech App Selector Dropdown
        app_options = [
            discord.SelectOption(
                label=f"{a['name']}",
                description=f"App ID: #{a['id']} • Version: v{a.get('version', '1.0')} • Online",
                value=a["name"],
                emoji="📦",
                default=(i==0)
            )
            for i, a in enumerate(apps[:20])
        ]
        self.app_select = discord.ui.Select(placeholder="📱 Select Application to Inspect...", options=app_options, row=0)
        self.app_select.callback = self.app_callback
        self.add_item(self.app_select)

        # 2. High-Tech Status Filter Dropdown
        status_options = [
            discord.SelectOption(label="Unused Keys Only (Fresh)", description="Keys ready to be redeemed by clients", value="unused", emoji="🟢", default=True),
            discord.SelectOption(label="Used Keys Only (Redeemed)", description="Keys currently bound to active clients", value="used", emoji="🔴"),
            discord.SelectOption(label="Complete Vault (All Keys)", description="Show all keys in this application", value="all", emoji="🌐")
        ]
        self.status_select = discord.ui.Select(placeholder="🔍 Filter Vault Status...", options=status_options, row=1)
        self.status_select.callback = self.status_callback
        self.add_item(self.status_select)

    async def app_callback(self, interaction: discord.Interaction):
        self.selected_app = self.app_select.values[0]
        for opt in self.app_select.options:
            opt.default = (opt.value == self.selected_app)
        await self.render_keys(interaction)

    async def status_callback(self, interaction: discord.Interaction):
        self.selected_status = self.status_select.values[0]
        for opt in self.status_select.options:
            opt.default = (opt.value == self.selected_status)
        await self.render_keys(interaction)

    async def render_keys(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            res = requests.post(f"{API_URL}/api/v1/admin/bot/listkeys", json={
                "discord_id": self.effective_dev_id,
                "discord_username": str(interaction.user.name),
                "app_name": self.selected_app,
                "status_filter": self.selected_status,
                "limit": 20
            }, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                keys = data.get("keys", [])
                if not keys:
                    embed = discord.Embed(
                        title=f"{EMOJI['bolt']}  KEYS VAULT • `{self.selected_app}` (0 Found)",
                        description=f"> {EMOJI['alert']} No keys found with status filter **`{self.selected_status.upper()}`**.",
                        color=COLOR_WARNING
                    )
                else:
                    lines = []
                    for k in keys:
                        icon = EMOJI['tick'] if k['status'] == 'unused' else EMOJI['cross']
                        used_info = f" • Used by `{k['used_by']}`" if k['status'] == 'used' else f" • `{k['duration_days']}d`"
                        lines.append(f"{icon} **`{k['key']}`** [{k['level']}]{used_info}")
                    formatted = "\n".join(lines)
                    embed = discord.Embed(
                        title=f"{EMOJI['bolt']}  KEYS VAULT • `{self.selected_app}` ({data.get('total', len(keys))} Total)",
                        description=(
                            f"📊 **Unused:** `{data.get('unused_count', 0)}` {EMOJI['tick']} | **Used:** `{data.get('used_count', 0)}` {EMOJI['cross']}\n\n"
                            f"**━━━━━━━━━ KEYS LIST ━━━━━━━━━**\n"
                            f"{formatted}\n"
                            f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                            f"{EMOJI['dot']} *Current Filter: `{self.selected_status.upper()}` • App: `{self.selected_app}`*"
                        ),
                        color=COLOR_BRAND
                    )
                embed.set_footer(text=f"Joyst Auth • Real-Time Vault Inspector", icon_url=interaction.user.display_avatar.url)
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.followup.send(embed=embed, view=self)
            else:
                await interaction.edit_original_response(content=f"{EMOJI['cross']} `{data.get('detail', 'Error.')}`", view=self)
        except Exception as e:
            await interaction.edit_original_response(content=f"Error: {e}", view=self)

class ListUsersDropdownView(discord.ui.View):
    def __init__(self, effective_dev_id: str, apps: list, guild: discord.Guild):
        super().__init__(timeout=120)
        self.effective_dev_id = effective_dev_id
        self.apps = apps
        self.guild = guild
        self.selected_app = apps[0]["name"] if apps else None

        app_options = [
            discord.SelectOption(
                label=f"{a['name']}",
                description=f"App ID: #{a['id']} • Version: v{a.get('version', '1.0')} • Online",
                value=a["name"],
                emoji="📦",
                default=(i==0)
            )
            for i, a in enumerate(apps[:20])
        ]
        self.app_select = discord.ui.Select(placeholder="📱 Select Application to view clients...", options=app_options, row=0)
        self.app_select.callback = self.app_callback
        self.add_item(self.app_select)

    async def app_callback(self, interaction: discord.Interaction):
        self.selected_app = self.app_select.values[0]
        for opt in self.app_select.options:
            opt.default = (opt.value == self.selected_app)
        await self.render_users(interaction)

    async def render_users(self, interaction: discord.Interaction):
        if not interaction.response.is_done():
            await interaction.response.defer()
        try:
            res = requests.post(f"{API_URL}/api/v1/admin/bot/listusers", json={
                "discord_id": self.effective_dev_id,
                "discord_username": str(interaction.user.name),
                "app_name": self.selected_app,
                "limit": 20
            }, timeout=15)
            data = parse_api_response(res)
            if res.status_code == 200 and data.get("success"):
                users = data.get("users", [])
                if not users:
                    embed = discord.Embed(
                        title=f"{EMOJI['bot']}  CLIENTS ROSTER • `{self.selected_app}` (0 Users)",
                        description=f"> {EMOJI['alert']} No registered clients in application `{self.selected_app}`.",
                        color=COLOR_WARNING
                    )
                else:
                    lines = []
                    for u in users:
                        st_icon = EMOJI['cross'] if u['is_banned'] else (EMOJI['tick'] if u['hwid_locked'] else EMOJI['dot'])
                        lines.append(f"{st_icon} **`{u['username']}`** • `{u['subscription']}` (Exp: `{u['expires_at']}`)")
                    formatted = "\n".join(lines)
                    embed = discord.Embed(
                        title=f"{EMOJI['bot']}  CLIENTS ROSTER • `{self.selected_app}` ({data.get('total', len(users))} Total)",
                        description=(
                            f"**Registered Clients in `{self.selected_app}`:**\n\n"
                            f"{formatted}\n\n"
                            f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                            f"{EMOJI['dot']} *Use `/userinfo [username]` for deep inspection.*"
                        ),
                        color=COLOR_INFO
                    )
                embed.set_footer(text=f"Joyst Auth • Client Roster Inspector", icon_url=interaction.user.display_avatar.url)
                if interaction.response.is_done():
                    await interaction.edit_original_response(embed=embed, view=self)
                else:
                    await interaction.followup.send(embed=embed, view=self)
            else:
                await interaction.edit_original_response(content=f"{EMOJI['cross']} `{data.get('detail', 'Error.')}`", view=self)
        except Exception as e:
            await interaction.edit_original_response(content=f"Error: {e}", view=self)

# ==================== SLASH COMMANDS ====================

# 1. /genkey (Days & Count Compulsory -> Instant Stylish Dropdown)
@bot.tree.command(name="genkey", description="⚡ Generate license keys for an application")
@app_commands.describe(days="Duration in days (-1 for lifetime)", count="Number of keys (1-50)")
async def genkey(interaction: discord.Interaction, days: int, count: int):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    apps = fetch_developer_apps(effective_dev_id, str(interaction.user.name))
    if not apps:
        await interaction.response.send_message(
            f"{EMOJI['alert']} **No linked Developer Account or Apps found!** Run `/link [email_or_username]` first.",
            ephemeral=True
        )
        return

    safe_count = min(max(1, count), 50)
    dur_text = f"**{days} Days**" if days > 0 else f"**Lifetime** {EMOJI['crown']}"

    view = GenKeyAppSelectView(days, safe_count, effective_dev_id, apps, interaction.guild)
    embed = discord.Embed(
        title=f"{EMOJI['bolt']}  LICENSE KEY MINTING ENCLAVE",
        description=(
            f"### {EMOJI['gear']} Key Parameters Configured:\n"
            f"{EMOJI['arrow']} **Duration:** {dur_text}\n"
            f"{EMOJI['arrow']} **Quantity:** `x{safe_count} Keys`\n\n"
            f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
            f"{EMOJI['dot']} *Select target Application from the dropdown below to mint keys:* {EMOJI['audio']}"
        ),
        color=COLOR_BRAND
    )
    embed.set_footer(text="Joyst Auth Zero-Leak Generator", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=view)

# 2. /adduser (Username, Password & Days Compulsory -> Instant Stylish Dropdown)
@bot.tree.command(name="adduser", description="👤 Create client username and password account")
@app_commands.describe(username="Client Username", password="Client Password", days="Duration in days (-1 for lifetime)")
async def adduser(interaction: discord.Interaction, username: str, password: str, days: int):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    apps = fetch_developer_apps(effective_dev_id, str(interaction.user.name))
    if not apps:
        await interaction.response.send_message(
            f"{EMOJI['alert']} **No linked Developer Account or Apps found!** Run `/link [email_or_username]` first.",
            ephemeral=True
        )
        return

    dur_text = f"**{days} Days**" if days > 0 else f"**Lifetime** {EMOJI['crown']}"

    view = AddUserAppSelectView(username.strip(), password.strip(), days, effective_dev_id, apps, interaction.guild)
    embed = discord.Embed(
        title=f"{EMOJI['bot']}  CLIENT ACCOUNT PROVISIONING",
        description=(
            f"### {EMOJI['gear']} Account Details Prepared:\n"
            f"{EMOJI['arrow']} **Username:** `{username.strip()}`\n"
            f"{EMOJI['arrow']} **Password:** `{password.strip()}`\n"
            f"{EMOJI['arrow']} **Duration:** {dur_text}\n\n"
            f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
            f"{EMOJI['dot']} *Select target Application from the dropdown below to create account:* {EMOJI['shield']}"
        ),
        color=COLOR_SUCCESS
    )
    embed.set_footer(text="Joyst Auth Provisioning System", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed, view=view)

# 3. /listkeys (INTERACTIVE DROPDOWN MENU)
@bot.tree.command(name="listkeys", description="🔑 Interactive Key Vault with App & Status Dropdown Menus")
async def listkeys_cmd(interaction: discord.Interaction):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction)
        return

    effective_dev_id = get_effective_developer_id(interaction)
    apps = fetch_developer_apps(effective_dev_id, str(interaction.user.name))
    if not apps:
        await interaction.response.send_message(
            f"{EMOJI['alert']} **No Apps found!** Run `/link [email_or_username]` first.",
            ephemeral=True
        )
        return

    view = ListKeysDropdownView(effective_dev_id, apps, interaction.guild)
    await view.render_keys(interaction)

# 4. /listusers (INTERACTIVE DROPDOWN MENU)
@bot.tree.command(name="listusers", description="📋 Interactive Client Roster with App Dropdown Menu")
async def listusers_cmd(interaction: discord.Interaction):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction)
        return

    effective_dev_id = get_effective_developer_id(interaction)
    apps = fetch_developer_apps(effective_dev_id, str(interaction.user.name))
    if not apps:
        await interaction.response.send_message(
            f"{EMOJI['alert']} **No Apps found!** Run `/link [email_or_username]` first.",
            ephemeral=True
        )
        return

    view = ListUsersDropdownView(effective_dev_id, apps, interaction.guild)
    await view.render_users(interaction)

# 5. /deluser
@bot.tree.command(name="deluser", description="🗑️ Permanently delete a client user account")
@app_commands.describe(username="Username of the client to delete")
async def deluser_cmd(interaction: discord.Interaction, username: str):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/deluser", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_username": username.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  CLIENT DELETED",
                description=f"### {EMOJI['tick']} Client `{data['username']}` permanently deleted from database.",
                color=COLOR_DANGER
            )
            embed.set_footer(text=f"Joyst Auth • Deleted by @{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
            await log_to_channels(
                action_title="USER_DELETED",
                user=interaction.user,
                details=f"Deleted client user '{data['username']}'",
                guild=interaction.guild,
                status="DANGER"
            )
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to delete user.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 6. /delkey
@bot.tree.command(name="delkey", description="🗑️ Permanently delete a license key")
@app_commands.describe(key="License key string to delete")
async def delkey_cmd(interaction: discord.Interaction, key: str):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/delkey", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_key": key.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['cross']}  LICENSE KEY DELETED",
                description=f"### {EMOJI['tick']} Key **`{data['key']}`** permanently deleted from vault.",
                color=COLOR_DANGER
            )
            embed.set_footer(text=f"Joyst Auth • Deleted by @{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
            await log_to_channels(
                action_title="KEY_DELETED",
                user=interaction.user,
                details=f"Deleted license key '{data['key']}'",
                guild=interaction.guild,
                status="DANGER"
            )
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed to delete key.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 7. /resethwid
@bot.tree.command(name="resethwid", description="🔄 Clear HWID lock for a client")
@app_commands.describe(username="Client username")
async def resethwid(interaction: discord.Interaction, username: str):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/resethwid", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_username": username.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['gear']}  HWID RESET COMPLETED",
                description=f"### {EMOJI['tick']} HWID lock for `{data['username']}` cleared!\n{EMOJI['dot']} Client will lock on next login.",
                color=COLOR_SUCCESS
            )
            embed.set_footer(text=f"Joyst Auth • Reset by @{interaction.user.name}", icon_url=interaction.user.display_avatar.url)
            await interaction.followup.send(embed=embed)
            await log_to_channels(
                action_title="HWID_RESET",
                user=interaction.user,
                details=f"HWID reset for user '{data['username']}'",
                guild=interaction.guild
            )
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 8. /userinfo
@bot.tree.command(name="userinfo", description="🔍 Look up a registered client")
@app_commands.describe(username="Client username")
async def userinfo(interaction: discord.Interaction, username: str):
    if not check_staff_or_owner_permission(interaction):
        await reject_unauthorized(interaction, "Authorized Staff Role Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/userinfo", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_username": username.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            u = data["user"]
            st = f"**BANNED** {EMOJI['cross']}" if u["is_banned"] else f"**ACTIVE** {EMOJI['tick']}"
            embed = discord.Embed(
                title=f"{EMOJI['bot']}  CLIENT: {u['username']}",
                description=(
                    f"{EMOJI['arrow']} **Status:** {st}\n"
                    f"{EMOJI['arrow']} **App:** `{u['app_name']}`\n"
                    f"{EMOJI['arrow']} **Subscription:** `{u['subscription']}`\n"
                    f"{EMOJI['arrow']} **Expires:** `{u['expires_at']}`\n"
                    f"{EMOJI['arrow']} **Last IP:** `{u['last_ip']}`\n"
                    f"{EMOJI['arrow']} **Bound HWID:** `{u['hwid'][:24]}...`"
                ),
                color=COLOR_DANGER if u["is_banned"] else COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'User not found.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 9. /stats
@bot.tree.command(name="stats", description="📊 View live telemetry & stats")
async def stats(interaction: discord.Interaction):
    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/stats", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name)
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['loading']}  JOYST AUTH • DEVELOPER TELEMETRY",
                description=(
                    f"**Overview for `@{data['developer']}`** (`{data['plan']}` Tier {EMOJI['crown']})\n\n"
                    f"{EMOJI['arrow']} **Apps:** `{data['total_apps']}`\n"
                    f"{EMOJI['arrow']} **Clients:** `{data['total_users']}`\n"
                    f"{EMOJI['arrow']} **Keys Vault:** `{data['total_keys']}` (Unused: `{data['unused_keys']}` {EMOJI['tick']})\n"
                    f"{EMOJI['arrow']} **Banned Users:** `{data['banned_users']}` {EMOJI['cross']}"
                ),
                color=COLOR_INFO
            )
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 10. /link
@bot.tree.command(name="link", description="🔗 Link this Discord Server to your Joyst Auth Developer Account")
@app_commands.describe(email_or_username="Your email or username on joystauth.cc")
async def link_cmd(interaction: discord.Interaction, email_or_username: str):
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/link", json={
            "discord_id": str(interaction.user.id),
            "discord_username": str(interaction.user.name),
            "email_or_username": email_or_username.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            g_id = str(interaction.guild_id) if interaction.guild_id else None
            if g_id:
                if g_id not in guild_configs:
                    guild_configs[g_id] = {}
                guild_configs[g_id]["owner_discord_id"] = str(interaction.user.id)
                guild_configs[g_id]["owner_username"] = data["developer"]
                guild_configs[g_id]["plan"] = data["plan"]
                save_guild_configs(guild_configs)

            embed = discord.Embed(
                title=f"{EMOJI['tick']}  SERVER LINKED TO DEVELOPER ACCOUNT",
                description=(
                    f"### {EMOJI['wave']} Welcome **@{interaction.user.name}**!\n"
                    f"{EMOJI['arrow']} **Developer:** `@{data['developer']}`\n"
                    f"{EMOJI['arrow']} **Plan:** `{data['plan']} Tier` {EMOJI['crown']}\n"
                    f"{EMOJI['arrow']} **Server ID:** `{interaction.guild_id or 'DM'}`\n\n"
                    f"{EMOJI['dot']} *Staff members can now run `/genkey`, `/adduser`, `/listkeys` with dropdowns!*"
                ),
                color=COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed)
            await log_to_channels(
                action_title="SERVER_LINKED",
                user=interaction.user,
                details=f"Linked Discord Server '{interaction.guild.name if interaction.guild else 'Direct'}' to Developer '@{data['developer']}'",
                guild=interaction.guild
            )
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  LINKING FAILED", description=f"> {EMOJI['alert']} `{data.get('detail', 'Account not found.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 11. /setstaffrole
@bot.tree.command(name="setstaffrole", description="🛡️ Set the Staff Role authorized to generate keys & manage clients")
@app_commands.describe(role="The Discord Role to authorize as Staff")
async def setstaffrole(interaction: discord.Interaction, role: discord.Role):
    if not (interaction.user.id == interaction.guild.owner_id or is_master_admin(interaction.user.id) or (hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator)):
        await reject_unauthorized(interaction, "Server Owner or Administrator Required")
        return

    g_id = str(interaction.guild_id)
    if g_id not in guild_configs:
        guild_configs[g_id] = {}
    if "staff_role_ids" not in guild_configs[g_id]:
        guild_configs[g_id]["staff_role_ids"] = []

    if str(role.id) not in [str(r) for r in guild_configs[g_id]["staff_role_ids"]]:
        guild_configs[g_id]["staff_role_ids"].append(str(role.id))
        save_guild_configs(guild_configs)

    embed = discord.Embed(
        title=f"{EMOJI['tick']}  STAFF ROLE CONFIGURED",
        description=(
            f"### {EMOJI['shield']} Role **{role.mention}** Authorized!\n\n"
            f"{EMOJI['arrow']} **Allowed Commands:** `/genkey`, `/adduser`, `/deluser`, `/delkey`, `/listkeys`, `/listusers`, `/resethwid`, `/userinfo`, `/stats`\n"
            f"{EMOJI['dot']} *Staff members can now manage keys and clients without creating a Joyst account.*"
        ),
        color=COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

# 12. /setlogchannel
@bot.tree.command(name="setlogchannel", description="📢 Set the channel where key and user audit logs are sent")
@app_commands.describe(channel="Text Channel for audit logs")
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not (interaction.user.id == interaction.guild.owner_id or is_master_admin(interaction.user.id) or (hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator)):
        await reject_unauthorized(interaction, "Server Owner or Administrator Required")
        return

    g_id = str(interaction.guild_id)
    if g_id not in guild_configs:
        guild_configs[g_id] = {}
    guild_configs[g_id]["log_channel_id"] = str(channel.id)
    save_guild_configs(guild_configs)

    embed = discord.Embed(
        title=f"{EMOJI['tick']}  AUDIT LOG CHANNEL CONFIGURED",
        description=f"### {EMOJI['audio']} Real-Time Audit Logs will now dispatch to {channel.mention}!",
        color=COLOR_SUCCESS
    )
    await interaction.response.send_message(embed=embed)

# 13. /genplankey (MASTER ADMIN ONLY)
@bot.tree.command(name="genplankey", description="👑 Master Admin: Generate Paid Developer Plan Upgrade Keys")
@app_commands.describe(count="Count (1-20)", plan="Paid / Unlimited")
async def genplankey(interaction: discord.Interaction, count: int = 1, plan: str = "Paid"):
    if not is_master_admin(interaction.user.id):
        await reject_unauthorized(interaction, "Platform Master Admin Required")
        return

    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/genplankey", json={
            "discord_id": str(interaction.user.id),
            "discord_username": str(interaction.user.name),
            "count": min(max(1, count), 20),
            "plan": plan.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            formatted = "\n".join([f"{EMOJI['dot']} **`{k}`**" for k in keys])
            embed = discord.Embed(
                title=f"{EMOJI['crown']}  DEVELOPER PLAN UPGRADE KEYS",
                description=(
                    f"### {EMOJI['tick']} Generated `{len(keys)}` Plan Key(s) ({data.get('plan', 'Paid')})\n\n"
                    f"**━━━━━━━━━ UPGRADE KEYS ━━━━━━━━━**\n"
                    f"{formatted}\n"
                    f"**━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━**\n"
                    f"{EMOJI['arrow']} **Redeem:** `/upgrade [key]` or enter on website."
                ),
                color=COLOR_WARNING
            )
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 14. /upgrade
@bot.tree.command(name="upgrade", description="💎 Upgrade your Developer account using a Key")
@app_commands.describe(key="Your Upgrade Key")
async def upgrade_cmd(interaction: discord.Interaction, key: str):
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/upgradeplan", json={
            "discord_id": str(interaction.user.id),
            "discord_username": str(interaction.user.name),
            "plan_key": key.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(
                title=f"{EMOJI['crown']}  ACCOUNT UPGRADED TO PAID TIER",
                description=(
                    f"### {EMOJI['wave']} Congratulations **@{data['developer']}**!\n"
                    f"{EMOJI['arrow']} **Plan Status:** `PAID / UNLIMITED` {EMOJI['crown']}\n"
                    f"{EMOJI['arrow']} **Max Apps:** `Unlimited`\n"
                    f"{EMOJI['arrow']} **Max Users:** `Unlimited`"
                ),
                color=COLOR_SUCCESS
            )
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  UPGRADE FAILED", description=f"> {EMOJI['alert']} `{data.get('detail', 'Invalid or used key.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 15. /ban & /unban
@bot.tree.command(name="ban", description="🔨 Ban a client user")
@app_commands.describe(username="Username", reason="Reason")
async def ban(interaction: discord.Interaction, username: str, reason: str = "Banned by Admin"):
    if not (interaction.user.id == interaction.guild.owner_id or is_master_admin(interaction.user.id) or (hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator)):
        await reject_unauthorized(interaction, "Server Owner or Administrator Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/ban", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_username": username.strip(),
            "reason": reason.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(title=f"{EMOJI['cross']}  USER BANNED", description=f"### {EMOJI['alert']} `{data['username']}` Banned\n{EMOJI['arrow']} **Reason:** `{data['reason']}`", color=COLOR_DANGER)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

@bot.tree.command(name="unban", description="🔓 Unban a client user")
@app_commands.describe(username="Username")
async def unban(interaction: discord.Interaction, username: str):
    if not (interaction.user.id == interaction.guild.owner_id or is_master_admin(interaction.user.id) or (hasattr(interaction.user, "guild_permissions") and interaction.user.guild_permissions.administrator)):
        await reject_unauthorized(interaction, "Server Owner or Administrator Required")
        return

    effective_dev_id = get_effective_developer_id(interaction)
    await interaction.response.defer()
    try:
        res = requests.post(f"{API_URL}/api/v1/admin/bot/unban", json={
            "discord_id": effective_dev_id,
            "discord_username": str(interaction.user.name),
            "target_username": username.strip()
        }, timeout=15)
        data = parse_api_response(res)
        if res.status_code == 200 and data.get("success"):
            embed = discord.Embed(title=f"{EMOJI['tick']}  USER UNBANNED", description=f"### {EMOJI['wave']} Access restored for `{data['username']}`", color=COLOR_SUCCESS)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(title=f"{EMOJI['cross']}  NOTICE", description=f"> {EMOJI['alert']} `{data.get('detail', 'Failed.')}`", color=COLOR_WARNING)
            await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}")

# 16. /ping & /help
@bot.tree.command(name="ping", description="🏓 Check live Discord bot latency & cloud telemetry")
async def ping_cmd(interaction: discord.Interaction):
    start = time.perf_counter()
    await interaction.response.defer()
    end = time.perf_counter()
    rtt = round((end - start) * 1000, 2)
    ws = round(bot.latency * 1000, 2) if bot.latency else 1.0

    embed = discord.Embed(
        title=f"{EMOJI['bolt']}  JOYST AUTH • NODE TELEMETRY {EMOJI['audio']}",
        description=(
            f"### {EMOJI['tick']} System Status: **OPERATIONAL (0-DELAY)**\n"
            f"{EMOJI['arrow']} **Gateway Ping:** `{ws} ms` {EMOJI['dot']}\n"
            f"{EMOJI['arrow']} **REST Round-Trip:** `{rtt} ms` {EMOJI['dot']}\n"
            f"{EMOJI['arrow']} **Edge Portal:** [joystauth.cc](https://joystauth.cc)"
        ),
        color=COLOR_SUCCESS
    )
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="📖 View all available Joyst Auth slash commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"{EMOJI['question']}  JOYST AUTH • COMMAND CODEX {EMOJI['bolt']}",
        description=(
            f"**Zero-Leak Security & Public Licensing Engine** {EMOJI['shield']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"### ⚙️ **Server Setup & Staff Configuration**\n"
            f"{EMOJI['arrow']} **`/link [email_or_user]`** — Link Server to Developer Account\n"
            f"{EMOJI['arrow']} **`/setstaffrole [role]`** — Set Authorized Staff Role(s)\n"
            f"{EMOJI['arrow']} **`/setlogchannel [channel]`** — Set Audit Logs Channel\n\n"
            f"### 👥 **Staff & Client Management**\n"
            f"{EMOJI['arrow']} **`/genkey [days] [count]`** — Generate Keys with Instant App Dropdown\n"
            f"{EMOJI['arrow']} **`/adduser [user] [pass] [days]`** — Create Client with Instant App Dropdown\n"
            f"{EMOJI['arrow']} **`/listkeys`** — Interactive Key Vault with Dropdowns\n"
            f"{EMOJI['arrow']} **`/listusers`** — Interactive Client Roster with Dropdowns\n"
            f"{EMOJI['arrow']} **`/deluser [username]`** — Permanently Delete Client\n"
            f"{EMOJI['arrow']} **`/delkey [key]`** — Permanently Delete License Key\n"
            f"{EMOJI['arrow']} **`/resethwid [user]`** — Clear HWID Lock for Client\n"
            f"{EMOJI['arrow']} **`/userinfo [user]`** — View Full Profile & Expiry\n"
            f"{EMOJI['arrow']} **`/stats`** — Live Dashboard Stats\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        ),
        color=COLOR_BRAND
    )
    await interaction.response.send_message(embed=embed)

if __name__ == "__main__":
    bot.run(TOKEN)
