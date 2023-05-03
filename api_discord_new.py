import os
from api_kittyai import KittyAIapi
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
import json
from io import BytesIO
import asyncio

ai = KittyAIapi(debug=False)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
discord_message_max_length = 2000

intents = discord.Intents.default()
intents.typing = False
intents.guilds = True
intents.messages = True
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# split up functions, to have separate functions for creating a new thread, processing the thread message history
async def get_thread_history(message):
    message_history = []
    async for msg in message.channel.history(oldest_first=True):
        if msg.type == discord.MessageType.thread_starter_message:
            thread_starter_message = msg.reference.resolved
            content = thread_starter_message.content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.append({"role": "assistant" if thread_starter_message.author.bot else "user", "content": content})
        else:
            content = msg.content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.append({"role": "assistant" if msg.author.bot else "user", "content": content})
    # return all messages except the last one, which is the message that triggered the bot
    return message_history[:-1]

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # get the new message
    new_message = message.content
    
    # if the message is posted in a thread of DM to the bot, get the thread message history
    create_new_thread = False
    if not message.channel.type == discord.ChannelType.text:
        message_history = await get_thread_history(message)
    else:
        message_history = []
        create_new_thread = True

    response = await ai.process_message(
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        new_message=new_message,
        previous_chat_history=message_history
    )

    messages = await ai.split_long_messages(response, discord_message_max_length)

    # create thread if necessary
    if create_new_thread:
        thread_name = await ai.get_thread_name(
            user_id=message.author.id,
            message=new_message
            )
        print(f"Creating new thread with name {thread_name}")
        thread = await message.create_thread(name=thread_name)
        await thread.send(messages[0])
        messages = messages[1:]
        
    for m in messages:
        await message.channel.send(m)
        # prevent hitting the ratelimit
        await asyncio.sleep(1)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()

# Run the bot
def run_bot():
    
    bot.run(DISCORD_BOT_TOKEN)
    

run_bot()


# TODO:
# 
# /setup
# /list_plugins
# /install_plugins
# /set_channel_location (admin only)
# /set_my_location
# /set_llm_model
# /install_plugin_gooogle_search
# /install_plugin_google_maps
# /install_plugin_youtube
# /channel_autorespond_off
# /channel_autorespond_on