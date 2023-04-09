import discord
from discord.ext import commands

import prompts
import api_openai

import os
import json
from dotenv import load_dotenv

load_dotenv()

####################
# Initialize the Discord bot
####################
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


####################
# Commands for the Discord bot
####################

# Command: /new_precise
@bot.tree.command(name="new_precise")
async def new_precise(interaction: discord.Interaction):
    channel_name = interaction.channel.name if interaction.channel.type != discord.ChannelType.private else str(interaction.user.id)
    bot.conversations[channel_name] = [{'role': 'system', 'content': prompts.precise}]
    bot.temperatures[channel_name] = 0
    await interaction.response.send_message("How can I help you now?")

# Command: /new_creative
@bot.tree.command(name="new_creative")
async def new_creative(interaction: discord.Interaction):
    channel_name = interaction.channel.name if interaction.channel.type != discord.ChannelType.private else str(interaction.user.id)
    bot.conversations[channel_name] = [{'role': 'system', 'content': prompts.creative}]
    bot.temperatures[channel_name] = 1
    await interaction.response.send_message("How can I help you now?")

# Command: /new_balanced
@bot.tree.command(name="new_balanced")
async def new_balanced(interaction: discord.Interaction):
    channel_name = interaction.channel.name if interaction.channel.type != discord.ChannelType.private else str(interaction.user.id)
    bot.conversations[channel_name] = [{'role': 'system', 'content': prompts.balanced}]
    bot.temperatures[channel_name] = 0.5
    await interaction.response.send_message("How can I help you now?")

# Command: /invite_user <username>
@bot.tree.command(name="invite_user")
async def invite_user(interaction: discord.Interaction, member: discord.Member):
    if str(interaction.user.id) in ADMIN_IDS:
        if member:
            user_id = member.id
            user_file = f"{user_id}.json"
            user_data = {"allowed_tokens": 100000, "used_tokens": 0}
            with open(user_file, "w") as f:
                json.dump(user_data, f)

            await interaction.response.send_message(f"{member.name} has now access to KittyAI.")
        else:
            await interaction.response.send_message("Sorry, couldn't find the username.")
    else:
        await interaction.response.send_message("Sorry, We are still working on this feature. Try again another day!")



####################
# Event: on_message
####################

@bot.event
async def on_message(message):
    if message.author.name == "Midjourney Bot" or message.author == bot.user:
        return

    if not message.content:
        return

    if isinstance(message.channel, discord.DMChannel):
        channel_name = str(message.author.id)
    else:
        channel_name = str(message.channel)
    if channel_name == 'text2image':
        async with message.channel.typing():
            ctx = await bot.get_context(message)

            # Prepare the messages parameter for the API call
            messages = [{'role': 'system','content': prompts.text2image},{'role': 'user','content': message.content}]

            assistant_response = api_openai.get_gpt4_response(messages, 1,message.author.id)

            # Send the GPT-4 response in the Discord channel
            await ctx.send(assistant_response)

    else:
        async with message.channel.typing():
            ctx = await bot.get_context(message)

            # Initialize conversation history and temperature if not already set
            if channel_name not in bot.conversations:
                bot.conversations[channel_name] = [{'role': 'system', 'content': prompts.precise}]
            if channel_name not in bot.temperatures:
                bot.temperatures[channel_name] = 0

            # Add the message to the conversation history
            bot.conversations[channel_name].append({
                'role': 'user',
                'content': message.content
            })

            # Prepare the messages parameter for the API call
            messages = [{"role": entry['role'], "content": entry['content']} for entry in bot.conversations[channel_name]]

            # Send a request to GPT-4
            assistant_response = api_openai.get_gpt4_response(messages,ctx.bot.temperatures[channel_name],message.author.id)

            # Split long responses into multiple messages
            split_responses = [assistant_response[i:i + 2000] for i in range(0, len(assistant_response), 2000)]

            # Add the GPT-4 response to the conversation history
            bot.conversations[channel_name].append({
                'role': 'assistant',
                'content': assistant_response
            })

            # Send the GPT-4 response in the Discord channel
            for response_part in split_responses:
                await ctx.send(response_part)

    await bot.process_commands(message)

# Event: on_ready
@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

    # Initialize conversation histories and temperatures
    bot.conversations = {}
    bot.temperatures = {}

    synced = await bot.tree.sync()

# Run the bot
def run_bot():
    bot.run(DISCORD_BOT_TOKEN)
