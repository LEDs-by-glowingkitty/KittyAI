import os
from api_kittyai import KittyAIapi
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()
import asyncio

ai = KittyAIapi(debug=False)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
discord_message_max_length = 1700 # max length of a Discord message, actually its 2000, but we want to be on the safe side

intents = discord.Intents.default()
intents.typing = False
intents.guilds = True
intents.messages = True
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

ongoing_tasks = {}

########################
## Helper functions
########################]

# check if autorespond is enabled for the channel or the channel in which the thread is inside
async def is_autorespond_enabled(message):
    channel_id = message.channel.id
    # if message is inside a thread, get the parent channel id
    if message.channel.type == discord.ChannelType.public_thread or message.channel.type == discord.ChannelType.private_thread:
        channel_id = message.channel.parent_id
    autorespond = await ai.get_channel_settings(channel_id, "autorespond")
    return autorespond

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
    last_sent_assistant_response = ""
    first_message = True
    is_code_block = False
    message_response = None
    send_new_message = False

    for item in response:
        if "content" in item['choices'][0]['delta']:
            partial_response = item['choices'][0]['delta']['content']
            # if message is too long, send it as a new message
            assistant_response += partial_response

            if partial_response.startswith("```") or partial_response.startswith("``"):
                is_code_block = not is_code_block

            if partial_response.endswith("\n") and is_code_block == False or partial_response.endswith("\n\n") and is_code_block == True:
                # if message is too long, send it as a new message
                if len(assistant_response) > discord_message_max_length:
                    send_new_message = True
                    # substract last_sent_assistant_response from assistant_response and send it as a new message
                    assistant_response = assistant_response.replace(last_sent_assistant_response, "")
            
                if first_message or send_new_message:
                    if thread:
                        message_response = await thread.send(assistant_response+"```" if is_code_block else assistant_response)
                    else:
                        message_response = await message.channel.send(assistant_response+"```" if is_code_block else assistant_response)
                    first_message = False
                    send_new_message = False
                else:
                    if message_response:
                        await message_response.edit(content=assistant_response+"```" if is_code_block else assistant_response)
                
                last_sent_assistant_response = assistant_response
                    

    if message_response:
        await message_response.edit(content=assistant_response)
    else:
        if thread:
            message_response = await thread.send(assistant_response+"```" if is_code_block else assistant_response)
        else:
            message_response = await message.channel.send(assistant_response+"```" if is_code_block else assistant_response)

    return message_response

async def ask(message):
    await message.add_reaction("💭")

    #TODO process plugins
    
    thread = None
    new_message = message.content
    create_new_thread_flag = True if message.channel.type == discord.ChannelType.text else False
    message_history = await get_thread_history(message) if not message.channel.type == discord.ChannelType.text else []

    if create_new_thread_flag:
        thread = await create_new_thread(message, new_message)

    response = await ai.ask(
        channel_id=str(message.channel.id),
        user_id=str(message.author.id),
        new_message=new_message,
        previous_chat_history=message_history
    )

    message_response = await send_response(message, response, thread)
    await message.remove_reaction("💭", bot.user)
    await message.add_reaction("✅")
    await bot.process_commands(message)

########################

########################
## Discord bot commands
########################

@bot.tree.command(name="reset_channel_settings", description="Resets all settings for this channel.")
async def reset_channel_settings(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM or thread, refuse to reset settings
    if not interaction.channel.type == discord.ChannelType.text:
        await interaction.response.send_message(f'You can only reset settings for channels, not DMs or threads.',ephemeral=True)
        return
    await ai.reset_channel_settings(channel_id=channel_id)
    await interaction.response.send_message(f'Reset all settings for **#{channel_name}**')


@bot.tree.command(name="reset_user_settings", description="Resets all settings for this user.")
async def reset_user_settings(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_name = interaction.user.name
    await ai.reset_user_settings(user_id=user_id)
    await interaction.response.send_message(f'We reset all your user settings, {user_name}',ephemeral=True)

#/get_channel_settings
@bot.tree.command(name="get_channel_settings", description="Gets all settings for this channel.")
async def get_channel_settings(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM or thread, refuse to get settings
    if not interaction.channel.type == discord.ChannelType.text:
        await interaction.response.send_message(f'You can only get settings for channels, not DMs or threads.',ephemeral=True)
        return
    channel_settings = await ai.get_channel_settings(channel_id=channel_id)
    await interaction.response.send_message(f'**#{channel_name}** settings: {channel_settings}',ephemeral=True)


#/get_user_settings (but only for the user who sent the command)
@bot.tree.command(name="get_my_settings", description="Gets all settings for this user.")
async def get_my_settings(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_settings = await ai.get_user_settings(user_id=user_id)
    # make response only visible to the user who sent the command
    await interaction.response.send_message(f'Your user settings:\n\n{str(user_settings)}', ephemeral=True)


@bot.tree.command(name="set_channel_autorespond_off", description="Turns off autorespond feature for this channel. use @KittyAI to get a response.")
async def set_channel_autorespond_off(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM or thread, refuse to turn off autorespond
    if not interaction.channel.type == discord.ChannelType.text:
        await interaction.response.send_message(f'You can only turn off auto respond for channels.',ephemeral=True)
        return
    await ai.update_channel_setting(channel_id=channel_id,setting= "autorespond",new_value=False)
    await interaction.response.send_message(f'Turned off auto respond for **#{channel_name}**. You can still mention **@KittyAI** in the channel, to get a response.')


@bot.tree.command(name="set_channel_autorespond_on",description="Turns on autorespond feature for this channel. KittyAI will respond to every message you send.")
async def set_channel_autorespond_on(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM or thread, refuse to turn on autorespond
    if not interaction.channel.type == discord.ChannelType.text:
        await interaction.response.send_message(f'You can only turn on auto respond for channels.',ephemeral=True)
        return
    await ai.update_channel_setting(channel_id=channel_id,setting= "autorespond",new_value=True)
    await interaction.response.send_message(f'Turned on auto respond for **#{channel_name}**. Every time you enter a message, **KittyAI** will respond.')


@bot.tree.command(name="get_channel_autorespond", description="Gets the autorespond setting for this channel.")
async def get_channel_autorespond(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM or thread, refuse to get autorespond
    if not interaction.channel.type == discord.ChannelType.text:
        await interaction.response.send_message(f'You can only get auto respond for channels.',ephemeral=True)
        return
    autorespond = await ai.get_channel_settings(channel_id=channel_id,setting= "autorespond")
    if autorespond == True:
        await interaction.response.send_message(f'💬 Auto respond for **#{channel_name}** is turned **on**. KittyAI will respond to every message you send.',ephemeral=True)
    else:
        await interaction.response.send_message(f'💬 Auto respond for **#{channel_name}** is turned **off**. You can still mention **@KittyAI** in the channel, to get a response.',ephemeral=True)


@bot.tree.command(name="set_channel_location", description="Sets the location for this channel. KittyAI will use this location to answer questions.")
async def set_channel_location(interaction: discord.Interaction, location: str):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'Please ask an admin to set the 📍 location for **#{channel_name}**.',ephemeral=True)
    else:
        await ai.update_channel_location(channel_id=channel_id,new_location=location)
        await interaction.response.send_message(f'📍 Location for **#{channel_name}** has been set to **{location}**.')


@bot.tree.command(name="get_channel_location", description="Gets the location for this channel.")
async def get_channel_location(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    location = await ai.get_channel_settings(channel_id=channel_id,setting= "location")
    if not location:
        await interaction.response.send_message(f'📍 Location for **#{channel_name}** has not been set.',ephemeral=True)
    else:
        await interaction.response.send_message(f'📍 Location for **#{channel_name}** is **{location}**.',ephemeral=True)


@bot.tree.command(name="set_my_location", description="Sets your location. KittyAI will use this location to answer questions.")
async def set_my_location(interaction: discord.Interaction, location: str):
    user_id = interaction.user.id
    await ai.update_user_location(user_id=user_id,new_location=location)
    await interaction.response.send_message(f'📍 Your location has been set to **{location}**.',ephemeral=True)


@bot.tree.command(name="get_my_location", description="Gets your location.")
async def get_my_location(interaction: discord.Interaction):
    user_id = interaction.user.id
    location = await ai.get_user_settings(user_id=user_id,setting= "location")
    if not location:
        await interaction.response.send_message(f'📍 Your location has not been set.',ephemeral=True)
    else:
        await interaction.response.send_message(f'📍 Your location is **{location}**.',ephemeral=True)

# /set_llm_model
# /install_plugin_gooogle_search
# /install_plugin_google_maps
# /install_plugin_youtube
# /google_search
# /google_images
# /youtube
# /google_maps


########################

########################
## Discord bot events
########################


@bot.event
async def on_message(message):
    global ongoing_tasks
    if message.author.bot:
        return
    
    # if autorespond is turned off for this channel, only respond if @KittyAI is mentioned
    if not await is_autorespond_enabled(message):
        if not bot.user in message.mentions:
            return

    if message.content.lower() in ["ok", "thanks", "stop"]:
        if str(message.author.id) in ongoing_tasks:
            ongoing_tasks[str(message.author.id)].cancel()
            del ongoing_tasks[str(message.author.id)]
        return

    if str(message.author.id) in ongoing_tasks:
        ongoing_tasks[str(message.author.id)].cancel()

    task = asyncio.create_task(
        ask(message)
    )
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