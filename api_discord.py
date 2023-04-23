import os
import api_openai
import api_google
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
import json
import prompts
from io import BytesIO



DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.typing = False
intents.guilds = True
intents.messages = True
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

search_results_start_message = "Here are some"

async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                return await resp.read()

# split up functions, to have separate functions for creating a new thread, processing the thread message history
async def prepare_threadhistory(message,new_message, message_history):
    async for msg in message.channel.history(oldest_first=True):
        if msg.type == discord.MessageType.thread_starter_message:
            thread_starter_message = msg.reference.resolved
            content = thread_starter_message.content.replace(f'<@{bot.user.id}>', '').strip()
            # filter out message that contain search results
            if not content.startswith(search_results_start_message):
                message_history.append({"role": "user", "content": content})
        else:
            content = msg.content.replace(f'<@{bot.user.id}>', '').strip()
            if not content.startswith(search_results_start_message):
                message_history.append({"role": "user", "content": content})
    message_history.append({"role": "user", "content": new_message})
    return message_history

async def process_commands(message):
    # if one of the following commans is in the message, execute the command
    # gs(query,resultspage) (examples: gs(what is the weather in berlin,1), gs(iphone 15)
    # gis(query,resultspage)

    # if message starts with command, execute the command
    files = []
    if message.startswith("gs("):
        # make sure the code doesn't crash if no comma is in the message
        if "," in message:
            query = message[3:].split(",")[0]
            resultspage = message[3:].split(",")[1].split(")")[0]
        else:
            query = message[3:].split(")")[0]
            resultspage = 1
        searchresults = await api_google.search(query, 4, resultspage)
        # create a new message, that contains a list of the search results, with the link linked to the title, in markdown format
        message = search_results_start_message+" search results I found for the query **" + query + "**\n\n"
        for result in searchresults:
            message += f"**[{result['title']}]({result['link']})**\n\n"

    if message.startswith("gis("):
        
        # make sure the code doesn't crash if no comma is in the message
        if "," in message:
            query = message[4:].split(",")[0]
            resultspage = message[4:].split(",")[1].split(")")[0]
        else:
            query = message[4:].split(")")[0]
            resultspage = 1
        searchresults = await api_google.searchimages(query, 4, resultspage)
        # create a new message, that contains a list of the search results, with the link linked to the title, in markdown format
        message = search_results_start_message+" images I found for the query **" + query + "**"
        
        for result in searchresults:
            try:
                file_data = await download_file(result['link'])
                file = discord.File(BytesIO(file_data), filename="image.png")
                files.append(file)
            except:
                #if the image coudn't be downloaded, skip it and print an error message
                print(f"Error downloading image: {result['link']}")
        
    return message, files
    
    

async def process_new_thread(message,new_message,message_history,gpt_temperature):
    # figure out what the thread is all about
    thread_name = api_openai.get_thread_name(new_message, message.author.id)

    # send the message to gpt4 and get the response
    message_history.append({"role": "user", "content": new_message})
    response_message = api_openai.get_gpt4_response(
        messages=message_history, 
        temperature=gpt_temperature, 
        user_id=message.author.id
        )
    # process if there are commands in the response and execute those commands if they exist
    response_message, files = await process_commands(response_message)
    thread = await message.channel.create_thread(name=thread_name, message=message)
    # send the message including attachments
    if files:
        await thread.send(response_message, files=files)
    else:
        await thread.send(response_message)

async def process_existing_thread(message,new_message,message_history,gpt_temperature):
    message_history = await prepare_threadhistory(message,new_message,message_history)

    response_message = api_openai.get_gpt4_response(
        messages=message_history, 
        temperature=gpt_temperature, 
        user_id=message.author.id
        )
    response_message, files = await process_commands(response_message)
    if files:
        await message.channel.send(response_message, files=files)
    else:
        await message.channel.send(response_message)

async def process_direct_message(message,new_message,message_history,gpt_temperature):
    # get the previous 5 messages in the DM history with the bot, if they exist and if the messages are not older than 12 hours
    async for msg in message.channel.history(limit=20, oldest_first=False):
        # only process if the message is not older than 12 hours
        if (message.created_at - msg.created_at).total_seconds() < 43200:
            message_history.append({"role": "user", "content": msg.content})

    print(message_history)
    # response_message = api_openai.get_gpt4_response(
    #     messages=message_history, 
    #     temperature=gpt_temperature, 
    #     user_id=message.author.id
    #     )
    # await message.channel.send(response_message)

async def get_channel_settings(channel_id):
    # load channel settings json
    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json') as f:
            channel_settings = json.load(f)

            if str(channel_id) in channel_settings["channels"]:
                return channel_settings["channels"][str(channel_id)]
            else:
                return None
    else:
        return None

@bot.tree.command(name="be_creative", description="Sets the GPT-4 temperature parameter to 1.0, for creative responses.")
async def be_creative(interaction: discord.Interaction):
    # write temperature to channel_settings.json
    channel_id = interaction.channel.id

    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                channel_settings["channels"][str(channel_id)]["system_prompt"] = prompts.creative
                channel_settings["channels"][str(channel_id)]["gpt_temperature"] = 1.0
            else:
                channel_settings["channels"][str(channel_id)] = {"system_prompt": prompts.creative, "gpt_temperature": 1.0, "autorespond": True}
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)

            await interaction.response.send_message(f'**KittyAI** is now being creative. You can use the **/be_precise** command to switch back to the nost precise responses.')
    else:
        channel_settings = {"channels": {str(channel_id): {"system_prompt": prompts.creative, "gpt_temperature": 1.0, "autorespond": True}}}
        with open('channel_settings.json', 'w') as file:
            json.dump(channel_settings, file)

        await interaction.response.send_message(f'**KittyAI** is now being creative. You can use the **/be_precise** command to switch back to the nost precise responses.')
        

@bot.tree.command(name="be_precise", description="Sets the GPT-4 temperature parameter to 0, for the most precise responses.")
async def be_creative(interaction: discord.Interaction):
    # write temperature to channel_settings.json
    channel_id = interaction.channel.id

    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                channel_settings["channels"][str(channel_id)]["system_prompt"] = prompts.precise
                channel_settings["channels"][str(channel_id)]["gpt_temperature"] = 0
            else:
                channel_settings["channels"][str(channel_id)] = {"system_prompt": prompts.precise, "gpt_temperature": 0, "autorespond": True}
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)

            await interaction.response.send_message(f'**KittyAI** is now being precise. You can use the **/be_creative** command to switch back to creative responses.')

    await interaction.response.send_message(f'**KittyAI** is now being precise. You can use the **/be_creative** command to switch back to creative responses.')


@bot.tree.command(name="set_systemprompt", description="Sets the system prompt for this channel, which will always be included before the user prompt.")
async def set_systemprompt(interaction: discord.Interaction, prompt: str):
    # write new system prompt to channel_settings.json
    channel_id = interaction.channel.id

    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                channel_settings["channels"][str(channel_id)]["system_prompt"] = prompt
            else:
                channel_settings["channels"][str(channel_id)] = {"system_prompt": prompt, "gpt_temperature": 0, "autorespond": True}
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)

    else:
        channel_settings = {"channels": {str(channel_id): {"system_prompt": prompt, "gpt_temperature": 0, "autorespond": True}}}
        with open('channel_settings.json', 'w') as file:
            json.dump(channel_settings, file)

    await interaction.response.send_message(f'**KittyAI** system prompt for the channel **{interaction.channel.name}** has been set to: {prompt}')


@bot.tree.command(name="reset_settings", description="Reset the settings for this channel to the default settings.")
async def reset_settings(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    
    # delete channel settings from channel_settings.json
    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                del channel_settings["channels"][str(channel_id)]
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)
    
    await interaction.response.send_message(f'**KittyAI** settings for the channel **{interaction.channel.name}** have been reset to the default settings.')


@bot.tree.command(name="get_settings", description="Show the settings for the current channel: System prompt, GPT-4 temperature, and autorespond status.")
async def get_settings(interaction: discord.Interaction):
    channel_settings = await get_channel_settings(interaction.channel.id)
    if channel_settings:
        await interaction.response.send_message(f'**System prompt:** {channel_settings["system_prompt"]}\n**GPT-4 temperature:** {channel_settings["gpt_temperature"]}\n**Autorespond:** {channel_settings["autorespond"]}')
    else:
        await interaction.response.send_message("No settings found for this channel.")


@bot.tree.command(name="autorespond_off", description="Turns off autorespond feature. KittyAI will only respond to messages when directly mentioned.")
async def autorespond_off(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name

    # change autorespond status in channel_settings.json
    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                channel_settings["channels"][str(channel_id)]["autorespond"] = False
            else:
                channel_settings["channels"][str(channel_id)] = {"system_prompt": prompts.precise, "gpt_temperature": 0, "autorespond": False}
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)
    else:
        channel_settings = {"channels": {str(channel_id): {"system_prompt": prompts.precise, "gpt_temperature": 0, "autorespond": False}}}
        with open('channel_settings.json', 'w') as file:
            json.dump(channel_settings, file)
    
    await interaction.response.send_message(f'Turned off auto respond for **#{channel_name}**. You can still mention **@KittyAI** in the channel, to get a response.')

@bot.tree.command(name="autorespond_on",description="Turns on autorespond feature. KittyAI will respond to every message you send.")
async def autorespond_on(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name

    # change autorespond status in channel_settings.json
    if os.path.exists('channel_settings.json'):
        with open('channel_settings.json', 'r') as file:
            channel_settings = json.load(file)
            if str(channel_id) in channel_settings["channels"]:
                channel_settings["channels"][str(channel_id)]["autorespond"] = True
            else:
                channel_settings["channels"][str(channel_id)] = {"system_prompt": prompts.precise, "gpt_temperature": 0, "autorespond": True}
            
            with open('channel_settings.json', 'w') as file:
                json.dump(channel_settings, file)
    else:
        channel_settings = {"channels": {str(channel_id): {"system_prompt": prompts.precise, "gpt_temperature": 0, "autorespond": True}}}
        with open('channel_settings.json', 'w') as file:
            json.dump(channel_settings, file)


    await interaction.response.send_message(f'Turned on auto respond for **#{channel_name}**. Every time you enter a message, **KittyAI** will respond.')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    channel_settings = await get_channel_settings(message.channel.id)
    channel_prompt = channel_settings["system_prompt"] if channel_settings else prompts.precise
    gpt_temperature = channel_settings["gpt_temperature"] if channel_settings else 0
    auto_respond_on = channel_settings["autorespond"] if channel_settings else True
    message_history = [{"role": "system", "content": channel_prompt}]
    new_message = message.content.replace(f'<@{bot.user.id}>', '').strip()
    
    # check if auto respond is turned on for the channel or if the bot was mentioned
    if auto_respond_on ==True or f'<@{bot.user.id}>' in message.content:
        # check if message is sent to bot directly in DMs
        if message.channel.type.name == "private":
            await process_direct_message(message,new_message,message_history,gpt_temperature)
        elif message.channel.type.name == "text":
            await process_new_thread(message,new_message,message_history,gpt_temperature)
        else:
            await process_existing_thread(message,new_message,message_history,gpt_temperature)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    await bot.tree.sync()

# Run the bot
def run_bot():
    bot.run(DISCORD_BOT_TOKEN)
    