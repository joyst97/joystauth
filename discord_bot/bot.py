import discord
from discord.ext import commands
from discord import app_commands
import requests
import json
import os

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        default_cfg = {
            "token": "YOUR_DISCORD_BOT_TOKEN_HERE",
            "api_url": "http://127.0.0.1:8000",
            "admin_token": "YOUR_JWT_ADMIN_TOKEN_HERE",
            "default_app_id": 1,
            "guild_id": None
        }
        with open(CONFIG_PATH, "w") as f:
            json.dump(default_cfg, f, indent=4)
        return default_cfg
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

config = load_config()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_headers():
    return {
        "Authorization": f"Bearer {config.get('admin_token', '')}",
        "Content-Type": "application/json"
    }

@bot.event
async def on_ready():
    print(f"[JOYST CORP AUTH BOT] Logged in as {bot.user.name} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"[JOYST CORP AUTH BOT] Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"[JOYST CORP AUTH BOT] Sync error: {e}")

# ==================== SLASH COMMANDS ====================

# 1. /genkey
@bot.tree.command(name="genkey", description="⚡ Instantly generate license keys for your Joyst Auth Application")
@app_commands.describe(
    days="Duration in days (-1 for lifetime)",
    count="Number of keys to generate (1-50)",
    level="Subscription Level / Rank (e.g. default, VIP)",
    app="Application Name (optional, defaults to primary app)"
)
async def genkey(interaction: discord.Interaction, days: int = 30, count: int = 1, level: str = "default", app: str = None):
    await interaction.response.defer(ephemeral=True)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "app_name": app,
        "count": min(max(1, count), 50),
        "duration_days": days,
        "level": level,
        "mask": "JOYST-XXXX-XXXX-XXXX"
    }

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json=payload, timeout=8)
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
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            err_msg = data.get("detail", data.get("message", "Key generation failed"))
            await interaction.followup.send(f"❌ **Error:** {err_msg}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Connection Error:** {str(e)}", ephemeral=True)

# 2. /adduser (Username + Password Direct Creation)
@bot.tree.command(name="adduser", description="👤 Create a client User & Password directly with subscription time")
@app_commands.describe(
    username="Client username to create",
    password="Client login password",
    days="Subscription duration in days (-1 for lifetime)",
    rank="Subscription Rank/Tier (e.g. default, VIP)",
    app="Application Name (optional)"
)
async def adduser(interaction: discord.Interaction, username: str, password: str, days: int = 30, rank: str = "default", app: str = None):
    await interaction.response.defer(ephemeral=True)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "app_name": app,
        "username": username.strip(),
        "password": password.strip(),
        "duration_days": days,
        "subscription_tier": rank
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/adduser", json=payload, timeout=8)
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
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'Failed to create user')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 3. /resethwid
@bot.tree.command(name="resethwid", description="🔄 Reset HWID lock for a specific user in your application")
@app_commands.describe(username="The client username whose HWID to reset")
async def resethwid(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name)
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/stats", json=payload, timeout=8)
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
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'Failed to fetch stats')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 7. /link
@bot.tree.command(name="link", description="🔗 Link your Discord to your Joyst Auth Developer Account (Google / Email)")
@app_commands.describe(email_or_username="Your email address or username registered on joystauth.cc")
async def link_cmd(interaction: discord.Interaction, email_or_username: str):
    await interaction.response.defer(ephemeral=True)
    payload = {
        "discord_id": str(interaction.user.id),
        "discord_username": str(interaction.user.name),
        "email_or_username": email_or_username.strip()
    }
    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/link", json=payload, timeout=8)
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
            embed.set_footer(text="You can now run /genkey, /stats, /ban, /resethwid from any channel!")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **Error:** {data.get('detail', 'Account not found')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Error:** {str(e)}", ephemeral=True)

# 8. /help
@bot.tree.command(name="help", description="📖 View all available Joyst Auth Discord commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Joyst Auth - Discord Bot Commands",
        description="Manage your auth system directly from Discord with these slash commands:",
        color=0xE11D48
    )
    embed.add_field(name="🔗 `/link [email_or_username]`", value="Link your Discord to your Google / Email Joyst account in 1-click.", inline=False)
    embed.add_field(name="👤 `/adduser [username] [password] [days] [rank] [app]`", value="Create user & password directly without needing license keys.", inline=False)
    embed.add_field(name="⚡ `/genkey [days] [count] [level] [app]`", value="Generate license keys instantly for your software.", inline=False)
    embed.add_field(name="🔄 `/resethwid [username]`", value="Clear HWID lock for a client so they can bind a new PC.", inline=False)
    embed.add_field(name="🔍 `/userinfo [username]`", value="Inspect a client's subscription expiry, rank, and HWID.", inline=False)
    embed.add_field(name="🔨 `/ban [username] [reason]`", value="Ban a client user from logging into your applications.", inline=False)
    embed.add_field(name="🔓 `/unban [username]`", value="Unban a previously blocked client account.", inline=False)
    embed.add_field(name="📊 `/stats`", value="View total apps, registered clients, and active keys summary.", inline=False)
    embed.set_footer(text="Joyst Auth Zero-Leak Infrastructure • joystauth.cc")
    await interaction.response.send_message(embed=embed, ephemeral=True)

if __name__ == "__main__":
    if config.get("token") and config["token"] != "YOUR_DISCORD_BOT_TOKEN_HERE":
        bot.run(config["token"])
    else:
        print("[JOYST CORP AUTH BOT] Please configure your Discord bot token in discord_bot/config.json")
