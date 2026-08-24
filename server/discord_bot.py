"""
JOYST AUTH — Official Discord Bot & Slash Commands Service
Supports: Guild Context (Servers) & User-Install Context (DMs / Anywhere)
"""
import os
import sys
import asyncio
import datetime
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

try:
    import discord
    from discord import app_commands
    from discord.ext import commands
except ImportError:
    print("[DISCORD BOT] discord.py is required. Install via: pip install discord.py")
    discord = None

from server.config import DISCORD_BOT_TOKEN, PLATFORM_NAME
from server.database import SessionLocal, Developer, Application, AppUser, LicenseKey

if discord:
    class JoystBot(commands.Bot):
        def __init__(self):
            intents = discord.Intents.default()
            super().__init__(command_prefix="!", intents=intents)

        async def setup_hook(self):
            try:
                print("[DISCORD BOT] Syncing application slash commands globally...")
                synced = await self.tree.sync()
                print(f"[DISCORD BOT] Global slash commands synchronized! ({len(synced)} commands ready)")
            except Exception as e:
                print(f"[DISCORD BOT] Slash commands sync notice: {e}")

        async def on_ready(self):
            print(f"[DISCORD BOT] Logged in successfully as {self.user} (ID: {self.user.id})")
            try:
                activity = discord.Activity(
                    type=discord.ActivityType.watching,
                    name="JOYST AUTH | joystauth.cc"
                )
                await self.change_presence(status=discord.Status.online, activity=activity)
                print("[DISCORD BOT] Presence status set to ONLINE!")
            except Exception as e:
                print(f"[DISCORD BOT] Presence error: {e}")

    bot = JoystBot()

    # 1. /stats command
    @bot.tree.command(name="stats", description="View live Joyst Auth platform infrastructure statistics")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_stats(interaction: discord.Interaction):
        db = SessionLocal()
        try:
            total_devs = db.query(Developer).count()
            total_apps = db.query(Application).count()
            total_users = db.query(AppUser).count()
            total_keys = db.query(LicenseKey).count()

            embed = discord.Embed(
                title="⚡ JOYST AUTH — Infrastructure Telemetry",
                description="Live multi-tenant software protection and HWID enclave status.",
                color=0xE11D48,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_thumbnail(url="https://joystauth.cc/static/img/joyst_logo.png")
            embed.add_field(name="👑 Developer Workspaces", value=f"**`{total_devs}`** Active", inline=True)
            embed.add_field(name="🛡️ Applications Protected", value=f"**`{total_apps}`** Enclaves", inline=True)
            embed.add_field(name="👥 Licensed Users", value=f"**`{total_users}`** Hardware-Bound", inline=True)
            embed.add_field(name="🔑 License Pool", value=f"**`{total_keys}`** Total Keys", inline=True)
            embed.add_field(name="🌐 Live Edge Portal", value="[joystauth.cc](https://joystauth.cc)", inline=True)
            embed.add_field(name="🔒 Cryptographic Shield", value="`AES-256-GCM + HWID`", inline=True)
            embed.set_footer(text="Joyst Corporation Auth • Next-Gen Protection")
            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

    # 2. /hwid_reset command
    @bot.tree.command(name="hwid_reset", description="Instantly reset a licensed user's hardware machine lock (HWID)")
    @app_commands.describe(username="The registered username of the user to reset")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_hwid_reset(interaction: discord.Interaction, username: str):
        db = SessionLocal()
        try:
            user = db.query(AppUser).filter(AppUser.username == username.strip()).first()
            if not user:
                await interaction.response.send_message(f"❌ User **`{username}`** was not found in the database.", ephemeral=True)
                return

            user.hwid = None
            db.commit()

            embed = discord.Embed(
                title="🔄 HWID Lock Reset Successful",
                description=f"Hardware ID binding for **`{username}`** has been cleared.\nThe user can now bind a brand new machine upon next login.",
                color=0x10B981,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Joyst Auth Security Core")
            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

    # 3. /user_info command
    @bot.tree.command(name="user_info", description="Lookup user license, HWID status, and expiry details")
    @app_commands.describe(username="The username to inspect")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_user_info(interaction: discord.Interaction, username: str):
        db = SessionLocal()
        try:
            user = db.query(AppUser).filter(AppUser.username == username.strip()).first()
            if not user:
                await interaction.response.send_message(f"❌ User **`{username}`** was not found.", ephemeral=True)
                return

            is_banned = bool(user.is_banned)
            hwid_display = user.hwid[:16] + "..." if user.hwid else "Unbound (Pending First Run)"
            expiry_display = user.expires_at.strftime("%Y-%m-%d %H:%M UTC") if user.expires_at else "Lifetime"

            embed = discord.Embed(
                title=f"👤 User Record: {user.username}",
                color=0xEF4444 if is_banned else 0x5865F2,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="📊 Status", value="🚫 **BANNED**" if is_banned else "🟢 **ACTIVE**", inline=True)
            embed.add_field(name="⏳ Subscription Expiry", value=f"`{expiry_display}`", inline=True)
            embed.add_field(name="🔒 HWID Binding", value=f"`{hwid_display}`", inline=False)
            embed.add_field(name="🌐 Last Login IP", value=f"`{user.last_ip or 'N/A'}`", inline=True)
            embed.add_field(name="📅 Created At", value=f"`{user.created_at.strftime('%Y-%m-%d')}`", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            db.close()

    # 4. /key_create command
    @bot.tree.command(name="key_create", description="Generate a new license key directly from Discord")
    @app_commands.describe(app_name="The name of your application", days="Subscription duration in days (e.g. 30)", note="Optional reference note")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_key_create(interaction: discord.Interaction, app_name: str, days: int, note: str = ""):
        db = SessionLocal()
        try:
            app = db.query(Application).filter(Application.name == app_name.strip()).first()
            if not app:
                await interaction.response.send_message(f"❌ Application **`{app_name}`** was not found.", ephemeral=True)
                return

            import secrets
            import string
            chars = string.ascii_uppercase + string.digits
            prefix = "JOYST-"
            key_code = prefix + "-".join("".join(secrets.choice(chars) for _ in range(4)) for _ in range(4))

            lic = LicenseKey(
                app_id=app.id,
                key=key_code,
                duration_days=days,
                level=1,
                note=note or f"Created via Discord by {interaction.user.name}",
                created_at=datetime.datetime.utcnow()
            )
            db.add(lic)
            db.commit()

            embed = discord.Embed(
                title="🔑 License Key Generated",
                description=f"New cryptographic license key created for **{app.name}**.",
                color=0xE11D48,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="🎟️ License Key", value=f"```\n{key_code}\n```", inline=False)
            embed.add_field(name="⏳ Duration", value=f"**{days} Days**", inline=True)
            embed.add_field(name="🛡️ Application", value=f"`{app.name}`", inline=True)
            embed.add_field(name="📝 Note", value=f"`{note or 'N/A'}`", inline=True)
            embed.set_footer(text="Joyst Auth Key Generation Engine")
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            db.close()

    # 5. /key_info command
    @bot.tree.command(name="key_info", description="Check status and details of a license key")
    @app_commands.describe(key="The license key to inspect")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_key_info(interaction: discord.Interaction, key: str):
        db = SessionLocal()
        try:
            lic = db.query(LicenseKey).filter(LicenseKey.key == key.strip()).first()
            if not lic:
                await interaction.response.send_message(f"❌ License Key **`{key}`** not found.", ephemeral=True)
                return

            app = db.query(Application).filter(Application.id == lic.app_id).first()
            app_name = app.name if app else "Unknown"

            embed = discord.Embed(
                title=f"🔑 License Record: {lic.key}",
                color=0x10B981 if not lic.is_used else 0x64748B,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="📊 Status", value="🔴 **USED / REDEEMED**" if lic.is_used else "🟢 **UNUSED / READY**", inline=True)
            embed.add_field(name="⏳ Duration", value=f"`{lic.duration_days} Days`", inline=True)
            embed.add_field(name="🛡️ App", value=f"`{app_name}`", inline=True)
            embed.add_field(name="👤 Bound User", value=f"`{lic.used_by_username or 'None'}`", inline=True)
            embed.add_field(name="📅 Created", value=f"`{lic.created_at.strftime('%Y-%m-%d')}`", inline=True)
            embed.add_field(name="📝 Note", value=f"`{lic.note or 'None'}`", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        finally:
            db.close()

    # 6. /ban_user command
    @bot.tree.command(name="ban_user", description="Ban a user from accessing protected software")
    @app_commands.describe(username="User to ban", reason="Reason for ban")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_ban_user(interaction: discord.Interaction, username: str, reason: str = "Violating Terms of Service"):
        db = SessionLocal()
        try:
            user = db.query(AppUser).filter(AppUser.username == username.strip()).first()
            if not user:
                await interaction.response.send_message(f"❌ User **`{username}`** not found.", ephemeral=True)
                return

            user.is_banned = True
            db.commit()

            embed = discord.Embed(
                title="🔨 User Banned Successfully",
                description=f"User **`{username}`** has been permanently banned from the enclave.",
                color=0xEF4444,
                timestamp=datetime.datetime.utcnow()
            )
            embed.add_field(name="Reason", value=f"`{reason}`", inline=False)
            embed.set_footer(text="Joyst Auth Moderation Engine")
            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

    # 7. /unban_user command
    @bot.tree.command(name="unban_user", description="Unban a previously banned user")
    @app_commands.describe(username="User to unban")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_unban_user(interaction: discord.Interaction, username: str):
        db = SessionLocal()
        try:
            user = db.query(AppUser).filter(AppUser.username == username.strip()).first()
            if not user:
                await interaction.response.send_message(f"❌ User **`{username}`** not found.", ephemeral=True)
                return

            user.is_banned = False
            db.commit()

            embed = discord.Embed(
                title="🔓 User Unbanned Successfully",
                description=f"User **`{username}`** has been restored and can now log in.",
                color=0x10B981,
                timestamp=datetime.datetime.utcnow()
            )
            embed.set_footer(text="Joyst Auth Moderation Engine")
            await interaction.response.send_message(embed=embed)
        finally:
            db.close()

    # 8. /help command
    @bot.tree.command(name="help", description="List all available Joyst Auth Discord commands")
    @app_commands.allowed_installs(guilds=True, users=True)
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    async def cmd_help(interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚡ JOYST AUTH — Command Codex",
            description="Available Slash Commands across Servers & Private DMs:",
            color=0xE11D48
        )
        embed.set_thumbnail(url="https://joystauth.cc/static/img/joyst_logo.png")
        embed.add_field(name="📊 `/stats`", value="Platform infrastructure & security telemetry", inline=False)
        embed.add_field(name="🔄 `/hwid_reset <username>`", value="Clear user machine lock for new PC", inline=False)
        embed.add_field(name="👤 `/user_info <username>`", value="Inspect subscription expiry & HWID", inline=False)
        embed.add_field(name="🔑 `/key_create <app> <days>`", value="Generate new license key instantly", inline=False)
        embed.add_field(name="🔍 `/key_info <key>`", value="Check key duration, status & owner", inline=False)
        embed.add_field(name="🔨 `/ban_user <username>`", value="Ban user from accessing applications", inline=False)
        embed.add_field(name="🔓 `/unban_user <username>`", value="Restore banned user access", inline=False)
        embed.set_footer(text="Next-Gen Software Protection • joystauth.cc")
        await interaction.response.send_message(embed=embed)

    def run_discord_bot():
        token = os.getenv("DISCORD_BOT_TOKEN") or DISCORD_BOT_TOKEN
        if not token or not token.strip():
            print("[DISCORD BOT ERROR] No DISCORD_BOT_TOKEN found in environment variables.")
            print("[DISCORD BOT HINT] Set DISCORD_BOT_TOKEN in your hosting environment variables or .env file.")
            return
        print("[DISCORD BOT] Starting Joyst Auth Discord Bot client...")
        try:
            bot.run(token.strip())
        except Exception as e:
            print(f"[DISCORD BOT FATAL ERROR] {e}")

if __name__ == "__main__":
    if discord:
        run_discord_bot()
    else:
        print("Please install discord.py: pip install discord.py")
