import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import cohere
import asyncio
from datetime import datetime

# Load config
with open("config.json") as f:
    config = json.load(f)

TOKEN = config["token"]
PREFIX = config["prefix"]
COHERE_API_KEY = config["cohere_api_key"]
OWNER_ID = config["owner_id"]

# Initialize Cohere V2 client
co = cohere.ClientV2(COHERE_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.dm_messages = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
tree = bot.tree

STATE_FILE = "state.json"
auto_chat_channels = {}
log_channel_id = None

warnings_data = {}
blacklist = set()

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

BAD_WORDS = {
    "porn", "sex", "sexy", "dildo", "blowjob", "handjob", "cum", "jizz", "boobs", "tits",
    "anal", "penis", "vagina", "nudes", "nude", "onlyfans", "threesome", "fingering",
    "masturbate", "orgasm", "hardcore", "hentai", "xxx", "clit", "cockring", "buttplug",
    "edging", "nsfw", "striptease", "camgirl", "camsex", "kinky", "fetish", "69", "bdsm",
    "deepthroat", "wetdream", "milf", "stepmom", "stepsis", "stepbro", "hump", "grope", "fuck", "shit", "bitch", "asshole", "damn", "bastard", 
    "dick", "pussy", "cock", "cunt", "fag", "motherfucker", "whore", "slut", "twat", "retard", "moron", "idiot", "dumbass",
    "loser", "jackass", "prick", "crap", "fuk", "fukk", "sh1t", "b1tch", "a55hole", "goon", "edge", "rule34", "r34",
    "pedo", "pedophile", "childporn", "cp", "loli", "shotacon", "shota", "underage", "minor", "kidporn", "babyfucker", "toddlercon", "younggirl",
    "youngboy", "childfuck", "preteen", "kindergirl", "kinderboy", "kill yourself", "suicide", "cutting", "terrorist", "bomb", "explosion", "nuke",
    "school shooter", "massacre", "murder", "stab", "rape", "rapist", "abuse", "gore",
    "blood", "violence", "slit", "decapitate", "torture", "isis", "nazism", "kkk",
    "heil", "fascist", "death to", "lynch", "execute", "hang yourself", "genocide", "nigger", 
    "niggers", "nigga", "niggas", "acab", "iran", "israel",
    "nga", "nazi", "hitler", "heil hitler", "kkk on top",
}

def contains_bad_words(message_content: str) -> bool:
    content_lower = message_content.lower()
    return any(bw in content_lower for bw in BAD_WORDS)

def is_admin():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            return False
        member = interaction.guild.get_member(interaction.user.id)
        return member.guild_permissions.administrator
    return app_commands.check(predicate)

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id == OWNER_ID
    return app_commands.check(predicate)

async def log_event(title: str, description: str, color=discord.Color.red()):
    if not log_channel_id:
        return
    channel = bot.get_channel(log_channel_id)
    if not channel:
        return
    embed = discord.Embed(title=title, description=description, color=color)
    embed.timestamp = datetime.utcnow()
    await channel.send(embed=embed)

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

async def blacklist_user(user: discord.User, auto=False, reason=None):
    user_id_str = str(user.id)
    if user_id_str in blacklist:
        return
    blacklist.add(user_id_str)
    save_state()

    try:
        appeal_msg = "Please appeal at: https://forms.gle/8tDoMfG17r39u7PR6"
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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print(f"In {len(bot.guilds)} guild(s)")
    total_members = sum(g.member_count for g in bot.guilds)
    print(f"Total members across guilds: {total_members}")
    print("--------------------------------------------------")
    await tree.sync()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id_str = str(message.author.id)
    guild_id_str = str(message.guild.id) if message.guild else None

    # Check blacklist first: block blacklisted users from auto chat channels
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

    # Delete messages with bad words, warn user, log, then return
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

    if isinstance(message.channel, discord.DMChannel):
        # Log DMs
        if log_channel_id:
            channel = bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(title="DM Logged", color=discord.Color.blue())
                embed.add_field(name="From", value=f"{message.author} ({message.author.id})", inline=False)
                embed.add_field(name="Message", value=message.content or "[No content]", inline=False)
                embed.timestamp = datetime.utcnow()
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass
        return

    # Auto chat handling - check blacklist again for safety
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

        # Use message.content as prompt and send AI response
        prompt = message.content
        try:
            response = co.chat(
                model="command-a-03-2025",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=150
            )
            reply = response.choices[0].message.content
            await message.channel.send(reply)
        except Exception as e:
            print(f"Error calling Cohere API: {e}")
        return

    await bot.process_commands(message)

@bot.command(name="mimi")
async def mimi(ctx, *, prompt: str):
    user_id_str = str(ctx.author.id)
    if user_id_str in blacklist:
        await ctx.reply("You are blacklisted from using this bot.")
        return
    if contains_bad_words(prompt):
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await warn_user(ctx.author, "Inappropriate language detected in command")
        await ctx.send(f"{ctx.author.mention}, your message contained inappropriate language and was removed.")
        return
    try:
        response = co.chat(
            model="command-a-03-2025",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150
        )
        reply = response.choices[0].message.content
        await ctx.send(reply)
    except Exception as e:
        await ctx.send("Sorry, an error occurred while processing your request.")

@tree.command(name="setautochatchannel", description="Set the auto chat channel for this server")
@is_admin()
async def setautochatchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id_str = str(interaction.guild_id)
    auto_chat_channels[guild_id_str] = channel.id
    save_state()
    await interaction.response.send_message(f"Auto chat channel set to {channel.mention}", ephemeral=True)

@tree.command(name="unsetautochatchannel", description="Unset the auto chat channel for this server")
@is_admin()
async def unsetautochatchannel(interaction: discord.Interaction):
    guild_id_str = str(interaction.guild_id)
    if guild_id_str in auto_chat_channels:
        del auto_chat_channels[guild_id_str]
        save_state()
        await interaction.response.send_message("Auto chat channel unset.", ephemeral=True)
    else:
        await interaction.response.send_message("No auto chat channel set for this server.", ephemeral=True)

@tree.command(name="setlogchannel", description="Set the log channel for this server")
@is_admin()
async def setlogchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    global log_channel_id
    log_channel_id = channel.id
    save_state()
    await interaction.response.send_message(f"Log channel set to {channel.mention}", ephemeral=True)

@tree.command(name="warn", description="Warn a user")
@is_admin()
async def warn(interaction: discord.Interaction, user: discord.User, *, reason: str):
    await warn_user(user, reason, warned_by=interaction.user)
    await interaction.response.send_message(f"{user} has been warned for: {reason}", ephemeral=True)

@tree.command(name="blacklist", description="Blacklist a user")
@is_admin()
async def blacklist_cmd(interaction: discord.Interaction, user: discord.User, *, reason: str = None):
    await blacklist_user(user, auto=False, reason=reason or "No reason provided")
    await interaction.response.send_message(f"{user} has been blacklisted.", ephemeral=True)

@tree.command(name="unblacklist", description="Unblacklist a user")
@is_admin()
async def unblacklist_cmd(interaction: discord.Interaction, user: discord.User):
    success = await unblacklist_user(user)
    if success:
        await interaction.response.send_message(f"{user} has been unblacklisted.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{user} is not blacklisted.", ephemeral=True)

@tree.command(name="warnings", description="Check warnings for a user")
@is_admin()
async def warnings(interaction: discord.Interaction, user: discord.User):
    count = warnings_data.get(str(user.id), 0)
    await interaction.response.send_message(f"{user} has {count} warning(s).", ephemeral=True)
    
@tree.command(name="listguilds", description="List all guilds the bot is in (Owner only)")
@is_owner()
async def listguilds(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    results = []

    for guild in bot.guilds:
        invite = "No invite permission"
        try:
            # Try to get an invite from the first available text channel
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


# general cmds

@tree.command(name="setstatus", description="Change the bot's status")
@is_owner()
@app_commands.describe(status="Status to set: online, idle, dnd, invisible")
async def setstatus(interaction: discord.Interaction, status: str):
    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible
    }
    if status.lower() not in status_map:
        await interaction.response.send_message("Invalid status. Choose: online, idle, dnd, invisible", ephemeral=True)
        return

    await bot.change_presence(status=status_map[status.lower()])
    await interaction.response.send_message(f"Bot status set to {status}.", ephemeral=True)

@tree.command(name="setactivity", description="Change the bot's activity/bio")
@is_owner()
@app_commands.describe(type="Activity type", text="Text to show (e.g., Playing X)")
async def setactivity(interaction: discord.Interaction, type: str, text: str):
    type_map = {
        "playing": discord.ActivityType.playing,
        "watching": discord.ActivityType.watching,
        "listening": discord.ActivityType.listening,
        "competing": discord.ActivityType.competing,
        "streaming": discord.ActivityType.streaming
    }
    if type.lower() not in type_map:
        await interaction.response.send_message("Invalid type. Choose: playing, watching, listening, competing, streaming", ephemeral=True)
        return

    activity = discord.Activity(type=type_map[type.lower()], name=text)
    await bot.change_presence(activity=activity)
    await interaction.response.send_message(f"Activity set to {type} {text}", ephemeral=True)

@tree.command(name="setpfp", description="Change the bot's profile picture")
@is_owner()
@app_commands.describe(image="New profile picture (image file)")
async def setpfp(interaction: discord.Interaction, image: discord.Attachment):
    if not image.content_type.startswith("image/"):
        await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
        return

    img_bytes = await image.read()
    try:
        await bot.user.edit(avatar=img_bytes)
        await interaction.response.send_message("Profile picture updated successfully.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Failed to update avatar: {e}", ephemeral=True)

@tree.command(name="setbanner", description="Change the bot's profile banner (only for verified bots)")
@is_owner()
@app_commands.describe(image="New banner image")
async def setbanner(interaction: discord.Interaction, image: discord.Attachment):
    if not image.content_type.startswith("image/"):
        await interaction.response.send_message("Please upload a valid image file.", ephemeral=True)
        return

    img_bytes = await image.read()
    try:
        await bot.user.edit(banner=img_bytes)
        await interaction.response.send_message("Banner updated successfully.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Failed to update banner: {e}", ephemeral=True)

@tree.command(name="setbio", description="Change the bot's 'About Me' profile text")
@is_owner()
@app_commands.describe(text="New bio text (max 190 chars)")
async def setbio(interaction: discord.Interaction, text: str):
    if len(text) > 190:
        await interaction.response.send_message("Bio too long. Max 190 characters.", ephemeral=True)
        return

    try:
        await bot.user.edit(about_me=text)
        await interaction.response.send_message("Bio updated successfully.", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"Failed to update bio: {e}", ephemeral=True)

@tree.command(name="getprofile", description="Get the profile info of any user")
@app_commands.describe(user="The user whose profile to show")
async def getprofile(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(thinking=True, ephemeral=True)

    user_profile = await fetch_user_profile(user.id)
    if not user_profile:
        await interaction.followup.send("Failed to fetch user profile.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"Profile of {user}",
        color=discord.Color.blue()
    )
    embed.add_field(name="Username", value=f"{user.name}#{user.discriminator}", inline=False)
    embed.add_field(name="User ID", value=user.id, inline=False)

    # Display Name from guild member if available
    member = None
    if interaction.guild:
        member = interaction.guild.get_member(user.id)
        if not member:
            try:
                member = await interaction.guild.fetch_member(user.id)
            except Exception:
                member = None

    if member:
        embed.add_field(name="Display Name", value=member.display_name, inline=False)

    # Bio (About Me)
    bio = user_profile.get("bio")
    if bio:
        embed.add_field(name="About Me", value=bio, inline=False)

    # Banner
    banner_hash = user_profile.get("banner")
    if banner_hash:
        # banner can be animated gif or png/jpeg
        if banner_hash.startswith("a_"):
            banner_url = f"https://cdn.discordapp.com/banners/{user.id}/{banner_hash}.gif?size=512"
        else:
            banner_url = f"https://cdn.discordapp.com/banners/{user.id}/{banner_hash}.png?size=512"
        embed.set_image(url=banner_url)
    else:
        embed.add_field(name="Banner", value="No banner set.", inline=False)

    embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

    await interaction.followup.send(embed=embed, ephemeral=True)


# Run the bot
bot.run(TOKEN)
