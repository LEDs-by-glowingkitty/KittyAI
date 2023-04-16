import os
import api_openai
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
import json
import prompts



DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.typing = False
intents.guilds = True
intents.messages = True
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

system_prompt = {"role": "system", "content": prompts.precise}

def auto_respond_on(channel_id):
    # load ignored channels json
    with open('autorespond_off.json') as f:
        ignored_channels = json.load(f)

        if str(channel_id) in ignored_channels["channels"]:
            return False
        else:
            return True

async def process_new_thread(message,new_message,message_history):
    # figure out what the thread is all about
    thread_name = api_openai.get_thread_name(new_message, message.author.id)

    # send the message to gpt4 and get the response
    message_history.append({"role": "user", "content": new_message})
    response_message = api_openai.get_gpt4_response(
        messages=message_history, 
        temperature=0, 
        user_id=message.author.id
        )
    thread = await message.channel.create_thread(name=thread_name, message=message)
    await thread.send(response_message)

async def process_existing_thread(message,new_message,message_history):
    async for msg in message.channel.history(oldest_first=True):
        if msg.type == discord.MessageType.thread_starter_message:
            thread_starter_message = msg.reference.resolved
            content = thread_starter_message.content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.append({"role": "user", "content": content})
        else:
            content = content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.append({"role": "user", "content": content})
    
    message_history.append({"role": "user", "content": new_message})
    response_message = api_openai.get_gpt4_response(
        messages=message_history, 
        temperature=0, 
        user_id=message.author.id
        )
    await message.channel.send(response_message)

@bot.tree.command(name="autorespond_off", description="Turns off autorespond feature. KittyAI will only respond to messages when directly mentioned.")
async def autorespond_off(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name

    if os.path.exists('autorespond_off.json'):
        with open('autorespond_off.json', 'r') as file:
            autorespond_off_channels = json.load(file)
    else:
        autorespond_off_channels = {"channels": []}

    if str(channel_id) not in autorespond_off_channels['channels']:
        autorespond_off_channels['channels'].append(str(channel_id))

        with open('autorespond_off.json', 'w') as file:
            json.dump(autorespond_off_channels, file)

        await interaction.response.send_message(f'Turned off auto respond for **#{channel_name}**. You can still mention **@KittyAI** in the channel, to get a response.')

@bot.tree.command(name="autorespond_on",description="Turns on autorespond feature. KittyAI will respond to every message you send.")
async def autorespond_on(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name

    if os.path.exists('autorespond_off.json'):
        with open('autorespond_off.json', 'r') as file:
            autorespond_off_channels = json.load(file)
    else:
        autorespond_off_channels = {"channels": []}

    if str(channel_id) in autorespond_off_channels['channels']:
        autorespond_off_channels['channels'].remove(str(channel_id))

        with open('autorespond_off.json', 'w') as file:
            json.dump(autorespond_off_channels, file)

        await interaction.response.send_message(f'Turned on auto respond for **#{channel_name}**. Every time you enter a message, **KittyAI** will respond.')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # if f'<@{bot.user.id}>' in message.content:
    message_history = [system_prompt]
    new_message = message.content.replace(f'<@{bot.user.id}>', '').strip()
    
    # check if auto respond is turned on for the channel or if the bot was mentioned
    if auto_respond_on(message.channel.id)==True or f'<@{bot.user.id}>' in message.content:
        if message.channel.type.name == "text":
            await process_new_thread(message,new_message,message_history)
        else:
            await process_existing_thread(message,new_message,message_history)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()

# Run the bot
def run_bot():
    bot.run(DISCORD_BOT_TOKEN)
    