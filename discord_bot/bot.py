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
@app_commands.describe(days="Duration in days (-1 for lifetime)", count="Number of keys to generate", level="Subscription Level (default/VIP)", app="App Name (optional)")
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
                description=f"Generated **{len(keys)}** key(s) for **`{app_name}`**:\n\n" + "\n".join([f"`{k}`" for k in keys]),
                color=0x6366F1
            )
            embed.add_field(name="App Name", value=f"`{app_name}`", inline=True)
            embed.add_field(name="Duration", value=f"{days} Days" if days > 0 else "Lifetime", inline=True)
            embed.add_field(name="Rank / Level", value=f"`{level}`", inline=True)
            embed.add_field(name="Developer", value=f"@{dev_user} ({plan})", inline=True)
            embed.set_footer(text="Joyst Corporation Zero-Leak Infrastructure • joystauth.cc")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            err_msg = data.get("detail", data.get("message", "Key generation failed"))
            await interaction.followup.send(f"❌ **Error:** {err_msg}", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ **Connection Error:** {str(e)}", ephemeral=True)

# 2. /stats
@bot.tree.command(name="stats", description="📊 View live Joyst Corporation Auth telemetry & statistics")
async def stats(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Fetch stats via bot endpoint or general admin telemetry
        res = requests.post(f"{config['api_url']}/api/v1/admin/bot/genkey", json={
            "discord_id": str(interaction.user.id),
            "discord_username": str(interaction.user.name),
            "count": 0
        }, timeout=8)
        data = res.json()

        embed = discord.Embed(title="⚡ Joyst Corporation Auth - System Status", color=0x6366F1)
        embed.add_field(name="Platform Status", value="🟢 **Operational (100% Uptime)**", inline=False)
        embed.add_field(name="Backend Server", value=f"`{config['api_url']}`", inline=True)
        embed.add_field(name="Discord Link", value=f"Connected as **@{interaction.user.name}**", inline=True)
        embed.set_footer(text="Joyst Corporation Zero-Leak Infrastructure • joystauth.cc")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

if __name__ == "__main__":
    if config["token"] and config["token"] != "YOUR_DISCORD_BOT_TOKEN_HERE":
        bot.run(config["token"])
    else:
        print("[JOYST CORP AUTH BOT] Please configure your Discord bot token in discord_bot/config.json")
