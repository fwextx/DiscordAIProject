# DiscordAIProject
Open Source Discord AI Bot Project 

## What you need:
- A Cohere API Key
- A Discord Bot Token

## How To Install
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
{
  "token": "Your Bot Token",
  "prefix": "!",
  "bot_status": "dnd",
  "bot_bio": "unused",
  "bot_status_message": "unused",
  "cohere_api_key": "COHERE-API",
  "owner_id": 1234567890
}

### Run the main file (bot.py)
