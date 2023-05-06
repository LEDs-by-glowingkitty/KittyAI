import os
from api_kittyai import KittyAIapi
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
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

ongoing_tasks = {}

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


async def create_new_thread(message, new_message):
    thread_name = await ai.get_thread_name(
        user_id=message.author.id,
        message=new_message
    )
    print(f"Creating new thread with name {thread_name}")
    thread = await message.create_thread(name=thread_name)
    return thread

async def send_response(message, response, thread=None):
    assistant_response = ""
    first_message = True
    is_code_block = False
    message_response = None

    for item in response:
        if "content" in item['choices'][0]['delta']:
            partial_response = item['choices'][0]['delta']['content']
            assistant_response += partial_response

            if partial_response.startswith("```") or partial_response.startswith("``"):
                is_code_block = not is_code_block

            if partial_response.endswith("\n") and is_code_block == False or partial_response.endswith("\n\n") and is_code_block == True:
                if first_message:
                    if thread:
                        message_response = await thread.send(assistant_response+"```" if is_code_block else assistant_response)
                    else:
                        message_response = await message.channel.send(assistant_response+"```" if is_code_block else assistant_response)
                    first_message = False
                else:
                    if message_response:
                        await message_response.edit(content=assistant_response+"```" if is_code_block else assistant_response)

    if message_response:
        await message_response.edit(content=assistant_response)
    else:
        message_response = await message.channel.send(assistant_response)

    return message_response

async def process_message(message):
    await message.add_reaction("💭")
    thread = None
    new_message = message.content
    create_new_thread_flag = True if message.channel.type == discord.ChannelType.text else False
    message_history = await get_thread_history(message) if not message.channel.type == discord.ChannelType.text else []

    if create_new_thread_flag:
        thread = await create_new_thread(message, new_message)

    response = await ai.process_message(
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        new_message=new_message,
        previous_chat_history=message_history
    )

    message_response = await send_response(message, response, thread)
    await message.remove_reaction("💭", bot.user)
    await message.add_reaction("✅")
    await bot.process_commands(message)

@bot.event
async def on_message(message):
    global ongoing_tasks
    if message.author.bot:
        return

    if message.content.lower() in ["ok", "thanks", "stop"]:
        if str(message.author.id) in ongoing_tasks:
            ongoing_tasks[str(message.author.id)].cancel()
            del ongoing_tasks[str(message.author.id)]
        return

    if str(message.author.id) in ongoing_tasks:
        ongoing_tasks[str(message.author.id)].cancel()

    task = asyncio.create_task(process_message(message))
    ongoing_tasks[str(message.author.id)] = task

    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        await message.remove_reaction("💭", bot.user)
        await message.add_reaction("✅")

        if str(message.author.id) in ongoing_tasks:
            del ongoing_tasks[str(message.author.id)]



#     # messages = await ai.split_long_messages(response, discord_message_max_length)
        
#     # for m in messages:
#     #     await message.channel.send(m)
#     #     # prevent hitting the ratelimit
#     #     await asyncio.sleep(1)

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
# - process gpt-4 response while its still running (to decrease response time)

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

# also add commands to use plugins directly, without LLM first have to process the message (for faster responses)
# except for creating a new thread (if the command is used outside of a thread)
# /google_search
# /google_images
# /youtube
# /google_maps