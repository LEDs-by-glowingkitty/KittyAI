import os
from api_kittyai import KittyAIapi
import discord
from discord.ext import commands
from discord import Thread
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
    async for msg in message.channel.history(oldest_first=False, limit=15):
        if msg.type == discord.MessageType.thread_starter_message:
            thread_starter_message = msg.reference.resolved
            content = thread_starter_message.content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.insert(0, {"role": "assistant" if thread_starter_message.author.bot else "user", "content": content})
        else:
            content = msg.content.replace(f'<@{bot.user.id}>', '').strip()
            message_history.insert(0,{"role": "assistant" if msg.author.bot else "user", "content": content})
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


async def ask(message,llm):
    await message.add_reaction("💭")

    #TODO process plugins
    
    thread = None
    new_message = message.content
    create_new_thread_flag = True if message.channel.type == discord.ChannelType.text else False
    message_history = await get_thread_history(message) if not message.channel.type == discord.ChannelType.text else []

    if create_new_thread_flag:
        thread = await create_new_thread(message, new_message)

    # if message is inside a thread and the thread is not saved under the channel settings, load settings from parent channel
    channel_id = str(message.channel.id)
    if message.channel.type == discord.ChannelType.public_thread or message.channel.type == discord.ChannelType.private_thread:
        if not await ai.channel_settings_exist(message.channel.id):
            channel_id = str(message.channel.parent_id)
        

    response = await ai.ask(
        channel_id=channel_id,
        user_id=str(message.author.id),
        new_message=new_message,
        previous_chat_history=message_history,
        llm_main_model=llm
    )

    message_response = await send_response(message, response, thread)
    await message.remove_reaction("💭", bot.user)
    await message.add_reaction("✅")
    await bot.process_commands(message)


########################

########################
## Discord bot commands
########################

########################
## Setup LLMs
########################

@bot.tree.command(name="setup_llm_openai_gpt_4", description="Setup OpenAI GPT-4 as your default LLM. The most powerful LLM from OpenAI.")
async def setup_llm_openai_gpt_4(interaction: discord.Interaction,openai_api_key:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the OpenAI GPT-4 API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_llm_openai_gpt_4(user_id=interaction.user.id,OPENAI_API_KEY=openai_api_key)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up OpenAI GPT-4 with your API key **"...{openai_api_key[-5:]}"** as your default LLM.'
    else:
        text = f'❌ Could not set up OpenAI GPT-4 with your API key **"...{openai_api_key[-5:]}"** as your default LLM. Please make sure the API key is correct and has access to the Open AI GPT-4 API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)


@bot.tree.command(name="setup_llm_openai_gpt_3_5_turbo", description="Setup OpenAI GPT-3.5 Turbo as your default LLM. The original ChatGPT model.")
async def setup_llm_openai_gpt_3_5_turbo(interaction: discord.Interaction,openai_api_key:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the OpenAI GPT-3.5 Turbo API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_llm_openai_gpt_3_5_turbo(user_id=interaction.user.id,OPENAI_API_KEY=openai_api_key)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up OpenAI GPT-3.5 Turbo with your API key **"...{openai_api_key[-5:]}"** as your default LLM.'
    else:
        text = f'❌ Could not set up OpenAI GPT-3.5 Turbo with your API key **"...{openai_api_key[-5:]}"** as your default LLM. Please make sure the API key is correct and has access to the Open AI GPT-3.5 Turbo API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)

########################

########################
## Setup plugins
########################

@bot.tree.command(name="setup_plugin_google", description="Setup the API keys for the Google plugin.")
async def setup_plugin_google(interaction: discord.Interaction,google_api_key:str,google_cx_id:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the Google API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_plugin_google(user_id=interaction.user.id,GOOGLE_API_KEY=google_api_key,GOOGLE_CX_ID=google_cx_id)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up the Google plugin with your API key **"...{google_api_key[-5:]}"** and your CX ID **"...{google_cx_id[-5:]}"**'
    else:
        text = f'❌ Could not set up the Google plugin with your API key **"...{google_api_key[-5:]}"** and your CX ID **"...{google_cx_id[-5:]}"**. Please make sure the API keys are correct and have access to the Google Search API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)


@bot.tree.command(name="setup_plugin_google_images", description="Setup the API keys for the Google Images plugin.")
async def setup_plugin_google_images(interaction: discord.Interaction,google_api_key:str,google_cx_id:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the Google API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_plugin_google(user_id=interaction.user.id,GOOGLE_API_KEY=google_api_key,GOOGLE_CX_ID=google_cx_id)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up the Google Images plugin with your API key **"...{google_api_key[-5:]}"** and your CX ID **"...{google_cx_id[-5:]}"**'
    else:
        text = f'❌ Could not set up the Google Images plugin with your API key **"...{google_api_key[-5:]}"** and your CX ID **"...{google_cx_id[-5:]}"**. Please make sure the API keys are correct and have access to the Google Search API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)


@bot.tree.command(name="setup_plugin_youtube", description="Setup the API key for the YouTube plugin.")
async def setup_plugin_youtube(interaction: discord.Interaction,google_api_key:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the YouTube API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_plugin_youtube(user_id=interaction.user.id,GOOGLE_API_KEY=google_api_key)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up the YouTube plugin with your API key **"...{google_api_key[-5:]}"**'
    else:
        text = f'❌ Could not set up the YouTube plugin with your API key **"...{google_api_key[-5:]}"**. Please make sure the API key is correct and has access to the YouTube Data API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)


@bot.tree.command(name="setup_plugin_google_maps", description="Setup the API key for the Google Maps plugin.")
async def setup_plugin_google_maps(interaction: discord.Interaction,google_api_key:str):
    if interaction.channel.type != discord.ChannelType.private:
        await interaction.response.send_message("I will check the Google Maps API key and let you know in a DM if it worked or not. One second...",ephemeral=True)
    success = await ai.setup_plugin_google_maps(user_id=interaction.user.id,GOOGLE_API_KEY=google_api_key)
    text = "Sorry, something went wrong."
    if success:
        text = f'✅ Successfully set up the Google Maps plugin with your API key **"...{google_api_key[-5:]}"**'
    else:
        text = f'❌ Could not set up the Google Maps plugin with your API key **"...{google_api_key[-5:]}"**. Please make sure the API key is correct and has access to the Google Maps API.'
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(text)
    else:
        await interaction.user.send(text)


########################


@bot.tree.command(name="reset_channel_settings", description="Resets all settings for this channel.")
async def reset_channel_settings(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'You need to be an administrator to reset settings for **#{channel_name}**',ephemeral=True)
        return
    
    await ai.reset_channel_settings(channel_id=channel_id)
    await interaction.response.send_message(f'Reset all settings for **#{channel_name}**')


@bot.tree.command(name="reset_my_settings", description="Resets all your user settings.")
async def reset_my_settings(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_name = interaction.user.name
    await ai.reset_user_settings(user_id=user_id)
    await interaction.response.send_message(f'We reset all your user settings, {user_name}',ephemeral=True)


@bot.tree.command(name="get_channel_settings", description="Gets all settings for this channel.")
async def get_channel_settings(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    channel_name = interaction.channel.name
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'You need to be an administrator to view the settings for this channel.',ephemeral=True)
        return

    if interaction.channel.type == discord.ChannelType.public_thread or interaction.channel.type == discord.ChannelType.private_thread:
        if not await ai.channel_settings_exist(interaction.channel.id):
            channel_id = str(interaction.channel.parent_id)
            channel_name = interaction.channel.parent.name

    channel_settings = await ai.get_channel_settings(channel_id=channel_id)
    await interaction.response.send_message(f'**#{channel_name}** settings: {channel_settings}',ephemeral=True)


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
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'You need to be an administrator to turn off auto respond for this channel.',ephemeral=True)
        return
    # if used in a private DM, refuse to turn off autorespond
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(f'Auto respond doesn\'t work for DMs.',ephemeral=True)
        return
    await ai.update_channel_setting(channel_id=channel_id,setting= "autorespond",new_value=False)
    await interaction.response.send_message(f'Turned off auto respond for **#{channel_name}**. You can still mention **@KittyAI** in the channel, to get a response.')


@bot.tree.command(name="set_channel_autorespond_on",description="Turns on autorespond feature for this channel. KittyAI will respond to every message you send.")
async def set_channel_autorespond_on(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'You need to be an administrator to turn on autorespond for this channel.',ephemeral=True)
        return
    # if used in a private DM, refuse to turn on autorespond
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(f'Auto respond doesn\'t work for DMs.',ephemeral=True)
        return
    await ai.update_channel_setting(channel_id=channel_id,setting= "autorespond",new_value=True)
    await interaction.response.send_message(f'Turned on auto respond for **#{channel_name}**. Every time you enter a message, **KittyAI** will respond.')


@bot.tree.command(name="get_channel_autorespond", description="Gets the autorespond setting for this channel.")
async def get_channel_autorespond(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if used in a private DM, refuse to get autorespond
    if interaction.channel.type == discord.ChannelType.private:
        await interaction.response.send_message(f'Auto respond doesn\'t work for DMs.',ephemeral=True)
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


    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'Please ask an admin to set the 📍 location for #{channel_name}.',ephemeral=True)
    # else if used in a thread and user is not an admin and also not the thread creator, refuse to set location
    
    # TODO: make sure only admins and thread/channel creators can set location, if outside of DM

    # elif (interaction.channel.type == discord.ChannelType.public_thread or interaction.channel.type == discord.ChannelType.private_thread) and not interaction.user.guild_permissions.administrator:
        # await interaction.response.send_message(f'Please ask an admin or the thread creator to set the 📍 location for #{channel_name}.',ephemeral=True)
    else:
        await ai.update_channel_location(channel_id=channel_id,new_location=location)
        await interaction.response.send_message(f'📍 Location for #{channel_name} has been set to {location}.')


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


@bot.tree.command(name="set_system_prompt", description="Sets the system prompt for this conversation. KittyAI will use this prompt to answer questions.")
async def set_system_prompt(interaction: discord.Interaction, prompt: str):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if the command is used in a public channel, make sure the user is an admin
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'Please ask an admin to set the 📝 system prompt for **#{channel_name}**.',ephemeral=True)
    else:
        await ai.update_channel_setting(channel_id=channel_id,setting= "llm_systemprompt",new_value=prompt)
        await interaction.response.send_message(f'📝 System prompt for **#{channel_name}** has been set to\n\n**{prompt}**.')


@bot.tree.command(name="get_system_prompt", description="Gets the system prompt for this conversation.")
async def get_system_prompt(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    prompt = await ai.get_channel_settings(channel_id=channel_id,setting= "llm_systemprompt")
    if not prompt:
        await interaction.response.send_message(f'📝 System prompt for **#{channel_name}** has not been set.',ephemeral=True)
    else:
        await interaction.response.send_message(f'📝 System prompt for **#{channel_name}** is\n\n**{prompt}**.',ephemeral=True)


@bot.tree.command(name="reset_system_prompt", description="Resets the system prompt for this conversation. Back to the default.")
async def reset_system_prompt(interaction: discord.Interaction):
    channel_id = interaction.channel.id
    channel_name = interaction.channel.name
    # if the command is used in a public channel, make sure the user is an admin
    if interaction.channel.type == discord.ChannelType.text and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(f'Please ask an admin to reset the 📝 system prompt for **#{channel_name}**.',ephemeral=True)
    else:
        await ai.reset_channel_setting(channel_id=channel_id,setting= "llm_systemprompt")
        await interaction.response.send_message(f'📝 System prompt for **#{channel_name}** has been reset to the default:\n\n**{await ai.get_channel_settings(channel_id=channel_id,setting="llm_systemprompt")}**.',ephemeral=True)




@bot.tree.command(name="google_search", description="Searches Google for the given query.")
async def google_search(interaction: discord.Interaction, query: str):
    # Use the ai.search_google function to search google
    google_api_key = await ai.get_api_key(user_id=interaction.user.id, key_type="GOOGLE_API_KEY")
    google_cx_id = await ai.get_api_key(user_id=interaction.user.id, key_type="GOOGLE_CX_ID")

    # If not all keys available, send a message to the user
    if not google_api_key or not google_cx_id:
        await interaction.response.send_message(f'Please setup Google Search first, via /setup_plugin_google', ephemeral=True)
        return

    results = await ai.search_google(
        google_api_key=google_api_key,
        google_cx_id=google_cx_id,
        query=query
    )

    # Send the results to the user
    await interaction.response.send_message(results)


# /google_images
@bot.tree.command(name="google_images", description="Searches Google Images for the given query.")
async def google_images(interaction: discord.Interaction, query: str):
    # use the ai.search_google function to search google
    google_api_key = await ai.get_api_key(user_id=interaction.user.id,key_type="GOOGLE_API_KEY")
    google_cx_id = await ai.get_api_key(user_id=interaction.user.id,key_type="GOOGLE_CX_ID")
    
    # if not all keys available, send a message to the user
    if not google_api_key or not google_cx_id:
        await interaction.response.send_message(f'Please setup Google Images first, via /setup_plugin_google_images',ephemeral=True)
        return
    
    results = await ai.search_google_images(
        google_api_key=google_api_key,
        google_cx_id=google_cx_id,
        query=query
        )
    # send the results to the user
    await interaction.response.send_message(results)

# /youtube
@bot.tree.command(name="youtube", description="Searches YouTube for the given query.")
async def youtube(interaction: discord.Interaction, query: str):
    # use the ai.search_google function to search google
    google_api_key = await ai.get_api_key(user_id=interaction.user.id,key_type="GOOGLE_API_KEY")
    
    # if not all keys available, send a message to the user
    if not google_api_key:
        await interaction.response.send_message(f'Please setup YouTube first, via /setup_plugin_youtube',ephemeral=True)
        return
    
    results = await ai.search_youtube_videos(
        google_api_key=google_api_key,
        query=query
        )
    # send the results to the user
    await interaction.response.send_message(results)


# /google_maps
@bot.tree.command(name="google_maps", description="Searches Google Maps for the given query.")
async def google_maps(interaction: discord.Interaction, query: str):
    # use the ai.search_google function to search google
    google_api_key = await ai.get_api_key(user_id=interaction.user.id,key_type="GOOGLE_API_KEY")
    
    # if not all keys available, send a message to the user
    if not google_api_key:
        await interaction.response.send_message(f'Please setup Google Maps first, via /setup_plugin_google_maps',ephemeral=True)
        return
    
    results = await ai.search_google_maps_locations(
        google_api_key=google_api_key,
        query=query
        )
    
    # send the results to the user
    await interaction.response.send_message(results)


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
        
    # if the channel has set a default llm and user has access to it, use it. Else, use the default llm from the user settings
    selected_llm = None
    channel_llm = await ai.get_channel_settings(channel_id=message.channel.id,setting= "llm_default_model")
    user_llm = await ai.get_user_settings(user_id=message.author.id,setting= "llm_default_model")
    if channel_llm and await ai.user_has_access_to_llm(user_id=message.author.id, llm=channel_llm):
        selected_llm = channel_llm
    elif user_llm and await ai.user_has_access_to_llm(user_id=message.author.id, llm=user_llm):
        selected_llm = user_llm
    else:
        if not await ai.get_user_settings(user_id=message.author.id,setting= "user_informed_about_missing_llm"):
            await message.author.send(f'It seems you haven\'t setup an LLM (large language model) yet, to chat with me. Please use the command `/setup_llm_...` and the name of the LLM you want to use.')
            await ai.update_user_setting(user_id=message.author.id,setting= "user_informed_about_missing_llm",new_value=True)
        return

    if message.content.lower() in ["ok", "thanks", "stop"]:
        if str(message.author.id) in ongoing_tasks:
            ongoing_tasks[str(message.author.id)].cancel()
            del ongoing_tasks[str(message.author.id)]
        return

    if str(message.author.id) in ongoing_tasks:
        ongoing_tasks[str(message.author.id)].cancel()

    task = asyncio.create_task(
        ask(
            message=message,
            llm=selected_llm
            )
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