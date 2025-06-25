# Discord AI Project
**DiscordAIProject is a simple-to-use, configurable Python framework that gives you everything you need to transform any Discord bot into an AI assistant. Whether you're developing a chatbot or a creative bot that talks as a character - Discord AI Project has it all!**

**When redistributing, you MUST credit the original owners.**

## What you need:
- Python 3.12
- A Cohere API Key
- A Discord Bot Token

## How To Install
**Disclaimer: This only works with Python 3.12**
### Setting Up a Virtual Environment (Recommended)
- Create the Virtual Enviroment
<pre>py -m venv DiscordAIProject</pre>
- Enable the Virtual Enviroment
<pre>DiscordAIProject\Scripts\activate</pre>

### Install Requirements
- On a Computer or Virtual Enviroment using Python 3.12, install discord.py and cohere:
<pre>pip install discord.py</pre> 
<pre>pip install cohere</pre>
### Configure the config.json file:
- Token: Your Bot Token
- Prefix: Your Bot Prefix (whether to use ! or ? for the bot)
- cohere_api_key: Your Cohere API Key (You can get one [here](https://dashboard.cohere.com/api-keys))
- owner_id: The Bot Owner User ID (Lets the Bot Owner configure the bot using the Admin Commands)
- bot_name: The Bot Name to use for Help commands, etc
- ban_appeal_link: The Ban Appeal Link to use, when you get banned by either Moderation or AI Moderation
- ai_command: The command to use to toggle the AI (Can't have spaces)
  
### Run the main file (bot.py)
<pre>py bot.py</pre>
