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
@bot.tree.command(name="genkey", description="Generate license keys for your Joyst Corporation application")
@app_commands.describe(days="Duration in days (-1 for lifetime)", count="Number of keys to generate", level="Subscription Level")
async def genkey(interaction: discord.Interaction, days: int = 30, count: int = 1, level: str = "default"):
    await interaction.response.defer(ephemeral=True)
    
    app_id = config.get("default_app_id", 1)
    payload = {
        "app_id": app_id,
        "count": min(max(1, count), 50),
        "duration_days": days,
        "level": level,
        "mask": "JOYST-XXXX-XXXX-XXXX",
        "notes": f"Generated via Discord Bot by {interaction.user.name}"
    }

    try:
        res = requests.post(f"{config['api_url']}/api/v1/admin/licenses", json=payload, headers=get_headers(), timeout=5)
        data = res.json()

        if res.status_code == 200 and data.get("success"):
            keys = data.get("keys", [])
            embed = discord.Embed(
                title="⚡ Joyst Corporation Auth - Keys Generated",
                description=f"Successfully generated **{len(keys)}** key(s):\n\n" + "\n".join([f"`{k}`" for k in keys]),
                color=0x6366F1
            )
            embed.add_field(name="Duration", value=f"{days} Days" if days > 0 else "Lifetime", inline=True)
            embed.add_field(name="Level / Rank", value=level, inline=True)
            embed.set_footer(text="Joyst Corporation Zero-Leak Infrastructure")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Error: {data.get('detail', data.get('message', 'Key generation failed'))}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Connection error: {str(e)}", ephemeral=True)

# 2. /resethwid
@bot.tree.command(name="resethwid", description="Reset Hardware ID (HWID) lock for a user")
@app_commands.describe(username="Username to reset HWID for")
async def resethwid(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    app_id = config.get("default_app_id", 1)

    try:
        users_res = requests.get(f"{config['api_url']}/api/v1/admin/users?app_id={app_id}&search={username}", headers=get_headers(), timeout=5)
        users_data = users_res.json()
        users = users_data.get("users", [])

        target = next((u for u in users if u["username"].lower() == username.lower()), None)
        if not target:
            await interaction.followup.send(f"❌ User `{username}` not found in application.", ephemeral=True)
            return

        reset_res = requests.post(f"{config['api_url']}/api/v1/admin/users/{target['id']}/reset-hwid", headers=get_headers(), timeout=5)
        res_data = reset_res.json()

        if reset_res.status_code == 200 and res_data.get("success"):
            embed = discord.Embed(
                title="🔄 HWID Reset Success",
                description=f"Hardware ID lock for **`{username}`** has been cleared successfully.\nUser can now log in on their new machine to bind.",
                color=0x10B981
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(f"❌ Failed: {res_data.get('detail', 'HWID reset failed')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Connection error: {str(e)}", ephemeral=True)

# 3. /userinfo
@bot.tree.command(name="userinfo", description="Look up user subscription, IP, and HWID status")
@app_commands.describe(username="Username to inspect")
async def userinfo(interaction: discord.Interaction, username: str):
    await interaction.response.defer(ephemeral=True)
    app_id = config.get("default_app_id", 1)

    try:
        res = requests.get(f"{config['api_url']}/api/v1/admin/users?app_id={app_id}&search={username}", headers=get_headers(), timeout=5)
        users = res.json().get("users", [])

        target = next((u for u in users if u["username"].lower() == username.lower()), None)
        if not target:
            await interaction.followup.send(f"❌ User `{username}` not found.", ephemeral=True)
            return

        embed = discord.Embed(title=f"👤 User Telemetry: {target['username']}", color=0x38BDF8)
        embed.add_field(name="Subscription", value=f"`{target['subscription']}`", inline=True)
        embed.add_field(name="Time Left", value=f"**{target['time_left']}**", inline=True)
        embed.add_field(name="HWID Bound", value="✅ Bound" if target['hwid'] else "❌ Unbound", inline=True)
        embed.add_field(name="Last IP", value=f"`{target['last_ip'] or 'N/A'}`", inline=True)
        embed.add_field(name="Account Status", value="🚫 Banned" if target['is_banned'] else "🟢 Active", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# 4. /banuser
@bot.tree.command(name="banuser", description="Ban a user from your application")
@app_commands.describe(username="Username to ban", reason="Reason for ban")
async def banuser(interaction: discord.Interaction, username: str, reason: str = "Banned via Discord"):
    await interaction.response.defer(ephemeral=True)
    app_id = config.get("default_app_id", 1)

    try:
        res = requests.get(f"{config['api_url']}/api/v1/admin/users?app_id={app_id}&search={username}", headers=get_headers(), timeout=5)
        users = res.json().get("users", [])
        target = next((u for u in users if u["username"].lower() == username.lower()), None)
        if not target:
            await interaction.followup.send(f"❌ User `{username}` not found.", ephemeral=True)
            return

        ban_res = requests.post(f"{config['api_url']}/api/v1/admin/users/{target['id']}/toggle-ban", json={"reason": reason}, headers=get_headers(), timeout=5)
        await interaction.followup.send(f"🚫 User `{username}` status updated: {ban_res.json().get('message')}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

# 5. /stats
@bot.tree.command(name="stats", description="View live Joyst Corporation Auth platform telemetry")
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        res = requests.get(f"{config['api_url']}/api/v1/admin/stats", headers=get_headers(), timeout=5)
        data = res.json().get("stats", {})

        embed = discord.Embed(title="⚡ Joyst Corporation Auth - System Telemetry", color=0x6366F1)
        embed.add_field(name="Total Applications", value=f"**{data.get('total_apps', 0)}**", inline=True)
        embed.add_field(name="Registered Users", value=f"**{data.get('total_users', 0)}**", inline=True)
        embed.add_field(name="Unused Licenses", value=f"**{data.get('unused_licenses', 0)}**", inline=True)
        embed.add_field(name="Logins Today", value=f"**{data.get('logins_today', 0)}**", inline=True)
        embed.add_field(name="HWID Blocks Today", value=f"**{data.get('failed_logins_today', 0)}**", inline=True)
        embed.add_field(name="Banned Users", value=f"**{data.get('banned_users', 0)}**", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    if config["token"] and config["token"] != "YOUR_DISCORD_BOT_TOKEN_HERE":
        bot.run(config["token"])
    else:
        print("[JOYST CORP AUTH BOT] Please configure your Discord bot token in discord_bot/config.json")
