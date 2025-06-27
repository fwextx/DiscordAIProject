import sys
import threading
import discord
from discord.ext import commands
from discord import app_commands
from discord import Embed
from discord import Status
from discord import ActivityType
from discord import Activity
import json
import os
import cohere
import asyncio
from datetime import datetime
import psutil
import platform
import time

# All credits to Matty and Extx (v4mp.matty and fwextx on discord)

# Load config
def load_config():
    global config, TOKEN, PREFIX, botname, COHERE_API_KEY, OWNER_ID, BAN_APPEAL_LINK, aicommand
    with open("config.json") as f:
        config = json.load(f)

    TOKEN = config["token"]
    PREFIX = config["prefix"]
    botname = config["bot_name"]
    COHERE_API_KEY = config["cohere_api_key"]
    OWNER_ID = config["owner_id"]
    BAN_APPEAL_LINK = config["ban_appeal_link"]
    aicommand = config["ai_command"]

# Initial load
load_config()

# Initialize Cohere V2 client
co = cohere.ClientV2(COHERE_API_KEY)

# Initialize Intents & Bot

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

# Initialize State.json and Blacklist Data

STATE_FILE = "state.json"
auto_chat_channels = {}
log_channel_id = None

warnings_data = {}
blacklist = set()

MEMORY_FILE = "memory.json"
memory = {}

# Load memory from file
def load_memory():
    global memory
    if os.path.isfile(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    else:
        memory = {}
# Save memory to file
def save_memory():
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=4)
save_memory()
print(f"[DEBUG] Loaded memory for {len(memory)} users")
def save_state():
    data = {
        "auto_chat_channels": auto_chat_channels,
        "log_channel_id": log_channel_id,
        "warnings_data": warnings_data,
        "blacklist": list(blacklist)
    }
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def load_state():
    global auto_chat_channels, log_channel_id, warnings_data, blacklist
    if os.path.isfile(STATE_FILE):
        with open(STATE_FILE) as f:
            data = json.load(f)
            auto_chat_channels = data.get("auto_chat_channels", {})
            log_channel_id = data.get("log_channel_id", None)
            warnings_data = data.get("warnings_data", {})
            blacklist = set(data.get("blacklist", []))
    else:
        auto_chat_channels = {}
        log_channel_id = None
        warnings_data = {}
        blacklist = set()

load_state()

# Example List of Bad Words to prevent people from saying.

BAD_WORDS = {
    "fuck", "bitch"
}

def contains_bad_words(message_content: str) -> bool:
    content_lower = message_content.lower()
    return any(bw in content_lower for bw in BAD_WORDS)

# Check if User is Admin

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        member = interaction.guild.get_member(interaction.user.id)
        return member.guild_permissions.administrator if member else False
    return app_commands.check(predicate)

# Check if User is Owner *(config.json - bot-owner)

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)

# Event Logging

async def log_event(title: str, description: str, color=discord.Color.red()):
    if not log_channel_id:
        return
    channel = bot.get_channel(log_channel_id)
    if not channel:
        return
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.utcnow()
    await channel.send(embed=embed)

# Automatic Warn System, for when the user says a bad word.

async def warn_user(user: discord.User, reason: str, warned_by: discord.User = None):
    user_id_str = str(user.id)
    current_warns = warnings_data.get(user_id_str, 0) + 1
    if current_warns > 3:
        current_warns = 3  # Cap warnings at 3
    warnings_data[user_id_str] = current_warns
    save_state()

    try:
        dm_msg = f"You have received a warning for the following reason:\n**{reason}**\n" \
                 f"Warning {current_warns} of 3."
        if current_warns >= 3:
            dm_msg += "\nYou have been blacklisted from using the bot services due to multiple warnings."
        await user.send(dm_msg)
    except Exception:
        pass

    warned_by_str = f" by {warned_by}" if warned_by else ""
    await log_event(
        title="User Warned",
        description=f"User: {user} ({user.id}){warned_by_str}\nReason: {reason}\nWarning {current_warns}/3"
    )

    if current_warns >= 3 and user_id_str not in blacklist:
        await blacklist_user(user, auto=True, reason="Exceeded maximum warnings")

# Blacklisting

async def blacklist_user(user: discord.User, auto=False, reason=None):
    user_id_str = str(user.id)
    if user_id_str in blacklist:
        return
    blacklist.add(user_id_str)
    save_state()

    try:
        appeal_msg = ("Please appeal here: " + BAN_APPEAL_LINK)
        if not auto:
            dm_msg = f"You have been blacklisted for the following reason:\n**{reason}**\n{appeal_msg}"
        else:
            dm_msg = f"You have been automatically blacklisted due to multiple warnings.\n{appeal_msg}"
        await user.send(dm_msg)
    except Exception:
        pass

    await log_event(
        title="User Blacklisted",
        description=f"User: {user} ({user.id})\nReason: {reason or 'Automatic blacklist due to warnings'}"
    )

async def unblacklist_user(user: discord.User):
    user_id_str = str(user.id)
    if user_id_str not in blacklist:
        return False
    blacklist.remove(user_id_str)
    if user_id_str in warnings_data:
        warnings_data[user_id_str] = 0
    save_state()
    await log_event(
        title="User Unblacklisted",
        description=f"User: {user} ({user.id})"
    )
    return True

# User Interface

@bot.event
async def on_ready():
    ascii_art = r"""

▓█████▄  ██▓  ██████  ▄████▄   ▒█████   ██▀███  ▓█████▄     ▄▄▄       ██▓    ██▓███   ██▀███   ▒█████   ▄▄▄██▀▀▀▓█████  ▄████▄  ▄▄▄█████▓
▒██▀ ██▌▓██▒▒██    ▒ ▒██▀ ▀█  ▒██▒  ██▒▓██ ▒ ██▒▒██▀ ██▌   ▒████▄    ▓██▒   ▓██░  ██▒▓██ ▒ ██▒▒██▒  ██▒   ▒██   ▓█   ▀ ▒██▀ ▀█  ▓  ██▒ ▓▒
░██   █▌▒██▒░ ▓██▄   ▒▓█    ▄ ▒██░  ██▒▓██ ░▄█ ▒░██   █▌   ▒██  ▀█▄  ▒██▒   ▓██░ ██▓▒▓██ ░▄█ ▒▒██░  ██▒   ░██   ▒███   ▒▓█    ▄ ▒ ▓██░ ▒░
░▓█▄   ▌░██░  ▒   ██▒▒▓▓▄ ▄██▒▒██   ██░▒██▀▀█▄  ░▓█▄   ▌   ░██▄▄▄▄██ ░██░   ▒██▄█▓▒ ▒▒██▀▀█▄  ▒██   ██░▓██▄██▓  ▒▓█  ▄ ▒▓▓▄ ▄██▒░ ▓██▓ ░ 
░▒████▓ ░██░▒██████▒▒▒ ▓███▀ ░░ ████▓▒░░██▓ ▒██▒░▒████▓     ▓█   ▓██▒░██░   ▒██▒ ░  ░░██▓ ▒██▒░ ████▓▒░ ▓███▒   ░▒████▒▒ ▓███▀ ░  ▒██▒ ░ 
 ▒▒▓  ▒ ░▓  ▒ ▒▓▒ ▒ ░░ ░▒ ▒  ░░ ▒░▒░▒░ ░ ▒▓ ░▒▓░ ▒▒▓  ▒     ▒▒   ▓▒█░░▓     ▒▓▒░ ░  ░░ ▒▓ ░▒▓░░ ▒░▒░▒░  ▒▓▒▒░   ░░ ▒░ ░░ ░▒ ▒  ░  ▒ ░░   
 ░ ▒  ▒  ▒ ░░ ░▒  ░ ░  ░  ▒     ░ ▒ ▒░   ░▒ ░ ▒░ ░ ▒  ▒      ▒   ▒▒ ░ ▒ ░   ░▒ ░       ░▒ ░ ▒░  ░ ▒ ▒░  ▒ ░▒░    ░ ░  ░  ░  ▒       ░    
 ░ ░  ░  ▒ ░░  ░  ░  ░        ░ ░ ░ ▒    ░░   ░  ░ ░  ░      ░   ▒    ▒ ░   ░░         ░░   ░ ░ ░ ░ ▒   ░ ░ ░      ░   ░          ░      
   ░     ░        ░  ░ ░          ░ ░     ░        ░             ░  ░ ░                 ░         ░ ░   ░   ░      ░  ░░ ░               
 ░                   ░                           ░                                                                     ░                 

    """
    print(ascii_art)
    print("-" * 50)
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"Guilds: {len(bot.guilds)}")
    total_members = sum(g.member_count for g in bot.guilds)
    print(f"Total members (combined): {total_members}")
    print (f"To view all console commands, type help in the console.")
    # Count and list commands loaded with checkmark or cross (cross for disabled? Here we just check if command is enabled)
    commands_loaded = list(bot.commands)
    print(f"Discord Commands loaded ({len(commands_loaded)}):")
    for cmd in commands_loaded:
        # Check if the command is enabled
        status = "✅" if not cmd.hidden and cmd.enabled else "❌"
        print(f" {status} {cmd.name}")
    print("-" * 50)
    threading.Thread(target=console_command_loop, daemon=True).start()
    await tree.sync()

# On Message Sent

@bot.event
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id_str = str(message.author.id)
    guild_id_str = str(message.guild.id) if message.guild else None


    if user_id_str in blacklist:
        if guild_id_str and guild_id_str in auto_chat_channels and message.channel.id == auto_chat_channels[guild_id_str]:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send("You are blacklisted from using this bot.")
            except Exception:
                pass
            return


    if contains_bad_words(message.content):
        try:
            await message.delete()
        except Exception:
            pass
        await warn_user(message.author, "Inappropriate language detected")
        await log_event(
            title="Bad Message Detected",
            description=f"User: {message.author} ({message.author.id})\nMessage: {message.content}"
        )
        return


    if message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return


    if guild_id_str and guild_id_str in auto_chat_channels and message.channel.id == auto_chat_channels[guild_id_str]:
        if user_id_str in blacklist:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send("You are blacklisted from using this bot.")
            except Exception:
                pass
            return

        # Call AI
        prompt = message.content
        try:
            response = co.chat(
                model="command-a-03-2025",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            content = response.message.content
            if isinstance(content, list):
                reply = " ".join(item.text for item in content).strip()
            else:
                reply = content.strip()
            await message.channel.send(reply)
        except Exception as e:
            print(f"[AI ERROR] {e}")
            await message.channel.send("")
        return

    await bot.process_commands(message)


    # Autochat handling
    if guild_id_str and guild_id_str in auto_chat_channels and message.channel.id == auto_chat_channels[guild_id_str]:
        if user_id_str in blacklist:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                await message.author.send("You are blacklisted from using this bot.")
            except Exception:
                pass
            return

        prompt = message.content

    await bot.process_commands(message)

# Warn User Command *(warn)

@tree.command(name="warn", description="Warn a user (owner)")
@is_owner()
@app_commands.describe(user="User to warn", reason="Reason for warning")
async def warn(interaction, user: discord.User, *, reason: str):
    if str(user.id) in blacklist:
        await interaction.response.send_message(f"{user.mention} is already blacklisted.", ephemeral=True)
        return
    await warn_user(user, reason, warned_by=interaction.user)
    await interaction.response.send_message(f"{user.mention} has been warned for: {reason}")

# Blacklist User *(blacklist)

@tree.command(name="blacklist", description="Blacklist a user (owner)")
@is_owner()
@app_commands.describe(user="User to blacklist", reason="Reason for blacklist (optional)")
async def blacklist_cmd(interaction, user: discord.User, *, reason: str = "No reason provided"):
    if str(user.id) in blacklist:
        await interaction.response.send_message(f"{user.mention} is already blacklisted.", ephemeral=True)
        return
    await blacklist_user(user, auto=False, reason=reason)
    await interaction.response.send_message(f"{user.mention} has been blacklisted.")

# Unblacklist User (unblacklist)

@tree.command(name="unblacklist", description="Remove a user from the blacklist (owner)")
@is_owner()
@app_commands.describe(user="User to unblacklist")
async def unblacklist_cmd(interaction, user: discord.User):
    success = await unblacklist_user(user)
    if success:
        await interaction.response.send_message(f"{user.mention} has been unblacklisted and warnings reset.")
    else:
        await interaction.response.send_message(f"{user.mention} is not blacklisted.", ephemeral=True)

# View Warnings for yourself or a user (warnings)

@tree.command(name="warnings", description="Check warnings for a user (or yourself)")
@app_commands.describe(user="User to check warnings for (optional)")
async def warnings_cmd(interaction, user: discord.User = None):
    if user is None:
        user = interaction.user
    warns = warnings_data.get(str(user.id), 0)
    await interaction.response.send_message(f"{user.mention} has {warns} warning(s).")

# Set the log channel (setlog)

@tree.command(name="setlog", description="Set the log channel (owner)")
@is_owner()
@app_commands.describe(channel="Channel to set as log")
async def setlog_cmd(interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    save_state()
    await interaction.response.send_message(f"Log channel set to {channel.mention}")

# Set the AutoChat Channel (Bot will respond to every message sent in the channel.)

@tree.command(name="setautochat", description="Set the auto chat channel")
@is_admin()
@app_commands.describe(channel="Channel to set as auto chat")
async def setautochat_cmd(interaction, channel: discord.TextChannel):
    guild_id_str = str(interaction.guild.id)
    auto_chat_channels[guild_id_str] = channel.id
    save_state()
    await interaction.response.send_message(f"Auto chat channel set to {channel.mention}")

# Remove the AutoChat Channel

@tree.command(name="removeautochat", description="Remove the auto chat channel")
@is_admin()
async def removeautochat_cmd(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild.id)
    if guild_id_str in auto_chat_channels:
        del auto_chat_channels[guild_id_str]
        save_state()
        await interaction.response.send_message("Auto chat channel removed.")
    else:
        await interaction.response.send_message("No auto chat channel set for this server.", ephemeral=True)

# Talk with the bot (Configure the command name in config.json)

@bot.command(name=aicommand)
async def d_aicommand(ctx, *, prompt: str):
    user_id = str(ctx.author.id)

    if user_id in blacklist:
        await ctx.send("You are blacklisted from using this bot.")
        return

    if user_id not in memory:
        memory[user_id] = []

    memory[user_id].append({"role": "user", "content": prompt})

    memory[user_id] = memory[user_id][-100:]

    try:
        response = co.chat(
            model="command-a-03-2025",
            messages=memory[user_id],
            temperature=0.7,
            max_tokens=300
        )
        content = response.message.content

        if isinstance(content, list):
            reply = " ".join(part.text for part in content if hasattr(part, "text")).strip()
        else:
            reply = content.strip()

        # Add bot reply to memory
        memory[user_id].append({"role": "assistant", "content": reply})
        memory[user_id] = memory[user_id][-10:]  # cap again

        save_memory()
        await ctx.send(reply)

    except Exception as e:
        print(f"[AI ERROR] {e}")
        save_memory()
        await ctx.send("Error contacting AI service. Please try again later.")

# List All Guilds the bot is in (listguilds)

@tree.command(name="listguilds", description="List all guilds the bot is in (Owner only)")
@is_owner()
async def listguilds(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    results = []

    for guild in bot.guilds:
        invite = "No invite permission"
        try:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).create_instant_invite:
                    invite_obj = await channel.create_invite(max_age=300, max_uses=1, unique=True, reason="Generated by owner command")
                    invite = invite_obj.url
                    break
        except Exception as e:
            invite = f"Error: {e}"

        results.append(f"**{guild.name}** (`{guild.id}`)\nInvite: {invite}")

    output = "\n\n".join(results) or "The bot is not in any guilds."
    # Discord messages max out at 2000 characters
    for chunk in [output[i:i+1900] for i in range(0, len(output), 1900)]:
        await interaction.followup.send(chunk, ephemeral=True)


# General Commands

@tree.command(name="setpresence", description="Set bot's status and activity (owner only)")
@is_owner()
@app_commands.describe(
    status="Bot status (online, idle, dnd, invisible)",
    activity_type="Activity type (playing, streaming, listening, watching, competing)",
    activity_name="Activity description"
)
@app_commands.choices(
    status=[
        app_commands.Choice(name="online", value="online"),
        app_commands.Choice(name="idle", value="idle"),
        app_commands.Choice(name="dnd", value="dnd"),
        app_commands.Choice(name="invisible", value="invisible"),
    ],
    activity_type=[
        app_commands.Choice(name="playing", value="playing"),
        app_commands.Choice(name="streaming", value="streaming"),
        app_commands.Choice(name="listening", value="listening"),
        app_commands.Choice(name="watching", value="watching"),
        app_commands.Choice(name="competing", value="competing"),
    ]
)
async def setpresence(
    interaction,
    status: app_commands.Choice[str],
    activity_type: app_commands.Choice[str],
    *,
    activity_name: str
):
    status_map = {
        "online": Status.online,
        "idle": Status.idle,
        "dnd": Status.dnd,
        "invisible": Status.invisible,
    }
    activity_type_map = {
        "playing": ActivityType.playing,
        "streaming": ActivityType.streaming,
        "listening": ActivityType.listening,
        "watching": ActivityType.watching,
        "competing": ActivityType.competing,
    }
    chosen_status = status_map[status.value]
    chosen_activity_type = activity_type_map[activity_type.value]

    activity = Activity(type=chosen_activity_type, name=activity_name)
    await interaction.client.change_presence(status=chosen_status, activity=activity)

    await interaction.response.send_message(
        f"Bot status set to **{status.value}** and activity to **{activity_type.value} {activity_name}**."
    )

    @app_commands.command(name="setpfp", description="Change the bot's profile picture (owner only)")
    @is_owner()
    @app_commands.describe(image="Image file for the new profile picture")
    async def setpfp(self, interaction, image: discord.Attachment):
        await interaction.response.defer()
        try:
            img_bytes = await image.read()
            await self.bot.user.edit(avatar=img_bytes)
            await interaction.followup.send("Bot profile picture updated successfully!")
        except Exception as e:
            await interaction.followup.send(f"Failed to update profile picture:\n{e}")

    @app_commands.command(name="setbio", description="Change the bot's bio/about me (owner only)")
    @is_owner()
    @app_commands.describe(bio="New bot bio/about me text")
    async def setbio(self, interaction, *, bio: str):
        await interaction.response.defer()
        try:
            await self.bot.user.edit(bio=bio)
            await interaction.followup.send("Bot bio/about me updated successfully!")
        except Exception as e:
            await interaction.followup.send(f"Failed to update bio:\n{e}")

    @app_commands.command(name="setbanner", description="Change the bot's banner image (owner only)")
    @is_owner()
    @app_commands.describe(image="Image file for the new banner")
    async def setbanner(self, interaction, image: discord.Attachment):
        await interaction.response.defer()
        try:
            img_bytes = await image.read()
            await self.bot.user.edit(banner=img_bytes)
            await interaction.followup.send("Bot banner updated successfully!")
        except Exception as e:
            await interaction.followup.send(f"Failed to update banner:\n{e}")
    
@tree.command(name="refreshcommands", description="Refresh (sync) all slash commands (Owner only)")
@is_owner()
async def refreshcommands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Sync commands globally
        await tree.sync()
        await interaction.followup.send("✅ Slash commands synced globally.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to sync commands: {e}", ephemeral=True)


@app_commands.command(name="botinfo", description="Show bot info")
async def botinfo(interaction: discord.Interaction):
    uptime_seconds = int(time.time() - bot.start_time)
    latency = round(bot.latency * 1000)
    embed = discord.Embed(title="Bot Info", color=discord.Color.blue())
    embed.add_field(name="Latency", value=f"{latency}ms")
    embed.add_field(name="Uptime", value=f"{uptime_seconds} seconds")
    embed.add_field(name="Python", value=platform.python_version())
    embed.add_field(name="Discord.py", value=discord.__version__)
    embed.set_footer(text=f"Bot ID: {bot.user.id}")
    await interaction.response.send_message(embed=embed)

    
    
    # MODERATION - GENERAL PURPOSE - THIS IS ONLY FOR SERVER MODERATION NOT FOR AI MODERATION.

@app_commands.command(name="mute", description="Mute a user for minutes")
@app_commands.checks.has_permissions(manage_roles=True)
async def mute(interaction, user: discord.Member, minutes: int = 10):
    guild = interaction.guild
    mute_role = discord.utils.get(guild.roles, name="Muted")
    if not mute_role:
        mute_role = await guild.create_role(name="Muted")
        for channel in guild.channels:
            await channel.set_permissions(mute_role, speak=False, send_messages=False, add_reactions=False)
    await user.add_roles(mute_role, reason=f"Muted by {interaction.user} for {minutes} minutes")
    await interaction.response.send_message(f"{user.mention} muted for {minutes} minutes.")
    await asyncio.sleep(minutes * 60)
    await user.remove_roles(mute_role, reason="Mute time expired")

@app_commands.command(name="kick", description="Kick a user from the server")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction, user: discord.Member, reason: str = "No reason provided"):
    await user.kick(reason=reason)
    await interaction.response.send_message(f"{user.mention} has been kicked. Reason: {reason}")

@app_commands.command(name="ban", description="Ban a user from the server")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction, user: discord.Member, reason: str = "No reason provided"):
    await user.ban(reason=reason)
    await interaction.response.send_message(f"{user.mention} has been banned. Reason: {reason}")

@app_commands.command(name="unban", description="Unban a user by their ID")
@app_commands.checks.has_permissions(ban_members=True)
async def unban(interaction, user_id: int):
    user = await bot.fetch_user(user_id)
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"User {user} has been unbanned.")

@app_commands.command(name="clear", description="Delete a number of messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction, amount: int = 5):
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"Deleted {len(deleted)} messages.", ephemeral=True)
    
    
    # help command

@tree.command(name="help", description="See all" + botname + "’s commands and what they do! 💕")
async def helpcmd(interaction: discord.Interaction):
    cmds = interaction.client.tree.get_commands()

    embed = Embed(
        title= ("🌸 " + botname +  " Help Menu 🌸"),
        description=("Here’s everything I can do! Use `/command` or try !" + aicommand + "  💬\n"),
        color=0xFFC0CB
    )

    general = ""
    moderation = ""
    owner = ""
    
    for cmd in cmds:
        if not isinstance(cmd, app_commands.Command): continue

        name = f"`/{cmd.name}`"
        desc = cmd.description or "No description."

        # Categorize
        if cmd.name in ["setpresence", "setpfp", "setbio", "setbanner", "refreshcommands", "listguilds", "setlog", "blacklist", "unblacklist"]:
            owner += f"🛠️ {name} — {desc}\n"
        elif cmd.name in ["warn", "kick", "ban", "unban", "mute", "clear", "warnings"]:
            moderation += f"🔨 {name} — {desc}\n"
        else:
            general += f"✨ {name} — {desc}\n"

    # Add sections
    if general:
        embed.add_field(name="🎀 General", value=general, inline=False)
    if moderation:
        embed.add_field(name="⚠️ Moderation", value=moderation, inline=False)
    if owner:
        embed.add_field(name="👑 Owner", value=owner, inline=False)

    embed.add_field(
        name="💬 Manual Commands",
        value=("• !" + aicommand +  " — Chat with " + botname +  " using plain text!\n"),
        inline=False
    )

    embed.set_footer(text="Use slash commands by typing '/' and choosing from the list ✨")

    await interaction.response.send_message(embed=embed)

def update_status(activity_type: str, activity_name: str, status: str = "online"):
    activity_type_map = {
        "playing": ActivityType.playing,
        "streaming": ActivityType.streaming,
        "listening": ActivityType.listening,
        "watching": ActivityType.watching,
        "competing": ActivityType.competing
    }

    status_map = {
        "online": Status.online,
        "idle": Status.idle,
        "dnd": Status.dnd,
        "invisible": Status.invisible
    }

    act_type = activity_type_map.get(activity_type.lower())
    stat = status_map.get(status.lower())

    if act_type is None or stat is None:
        print("❌ Invalid activity type or status.")
        return

    activity = Activity(type=act_type, name=activity_name)
    coro = bot.change_presence(status=stat, activity=activity)
    asyncio.run_coroutine_threadsafe(coro, bot.loop)
    print(f"✅ Status updated to {status}, {activity_type} {activity_name}")


def console_command_loop():
    while True:
        cmd = input(">>> ").strip().lower()

        if cmd == "help":
            print("""
Console Commands:
    help         - Show all commands
    restart      - Restart the bot
    stop         - Shutdown the bot
    reloadconfig - Reload config.json
    guilds       - List all guilds the bot is in
    users        - Count total unique users
    systeminfo   - Show CPU, RAM, and Disk usage
    setstatus    - Set the bot status (Syntax: setstatus [online|idle|dnd|invisible] [playing|listening|watching|...] [activity])
    flushmemory  - Clean the bots memory
""")
        elif cmd == "restart":
            print("Restarting bot...")
            os.execv(sys.executable, ['python'] + sys.argv)
        elif cmd == "stop":
            print("Shutting down bot...")
            os._exit(0)
        elif cmd == "reloadconfig":
            try:
                load_config()
                print("✅ Config reloaded successfully.")
            except Exception as e:
                print(f"❌ Failed to reload config: {e}")
        elif cmd == "guilds":
            print("Guilds I'm in:")
            for guild in bot.guilds:
                print(f"- {guild.name} (ID: {guild.id}) | Members: {guild.member_count}")
            print(f"Total: {len(bot.guilds)} guilds")

        elif cmd == "users":
            users = set()
            for guild in bot.guilds:
                for member in guild.members:
                    users.add(member.id)
            print(f"Total unique users across all guilds: {len(users)}")

        elif cmd == "systeminfo":
            cpu = psutil.cpu_percent(interval=1)
            ram = psutil.virtual_memory().percent
            disk = psutil.disk_usage('/').percent
            print("System Info:")
            print(f"CPU Usage:    {cpu}%")
            print(f"RAM Usage:    {ram}%")
            print(f"Disk Usage:   {disk}%")
        elif cmd == "flushmemory":
            memory.clear()
            save_memory()
            print("✅ Memory cleared.")
        elif cmd.startswith("setstatus"):
            try:
                parts = cmd.split(" ", 3)
                if len(parts) < 4:
                    print("Usage: setstatus [online|idle|dnd|invisible] [playing|listening|watching|...] [activity]")
                else:
                    _, status, activity_type, activity_name = parts
                    update_status(activity_type, activity_name, status)
            except Exception as e:
                print(f"❌ Failed to update status: {e}")

        else:
            print(f"Unknown command: {cmd}")

# Run the bot
bot.run(TOKEN)
