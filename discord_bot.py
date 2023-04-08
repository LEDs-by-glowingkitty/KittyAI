import discord
from discord.ext import commands
import openai
import traceback
import os
from dotenv import load_dotenv
load_dotenv()

# Set up your Discord bot token and OpenAI API key
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize the Discord bot and OpenAI
intents = discord.Intents.default()
intents.typing = False
intents.presences = False
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
openai.api_key = OPENAI_API_KEY

system_prompt_precise = {'role': 'system','content': "You are a helpful assistant. Keep your answers as short and precise as possible."}
system_prompt_creative = {'role': 'system','content': "You are a helpful and creative assistant."}
system_prompt_balanced = {'role': 'system','content': "You are a helpful assistant."}


# Command: /new_precise
@bot.tree.command(name="new_precise")
async def new_precise(interaction: discord.Interaction):
    channel_name = interaction.channel.name
    bot.conversations[channel_name] = [system_prompt_precise]
    bot.temperatures[channel_name] = 0
    await interaction.response.send_message("How can I help you now?")

# Command: /new_creative
@bot.tree.command(name="new_creative")
async def new_creative(interaction: discord.Interaction):
    channel_name = interaction.channel.name
    bot.conversations[channel_name] = [system_prompt_creative]
    bot.temperatures[channel_name] = 1
    await interaction.response.send_message("How can I help you now?")

# Command: /new_balanced
@bot.tree.command(name="new_balanced")
async def new_balanced(interaction: discord.Interaction):
    channel_name = interaction.channel.name
    bot.conversations[channel_name] = [system_prompt_balanced]
    bot.temperatures[channel_name] = 0.5
    await interaction.response.send_message("How can I help you now?")

# Event: on_message
@bot.event
async def on_message(message):
    if message.author.name == "Midjourney Bot" or message.author == bot.user:
        return
    
    if not message.content:
        return

    channel_name = str(message.channel)
    if channel_name == 'text2image':
        async with message.channel.typing():
            try:
                ctx = await bot.get_context(message)

                # Prepare the messages parameter for the API call
                messages = [{
                    'role': 'system',
                    'content': 'You are a text to image prompt engineer. I give you a prompt, and you create a much better prompt based on the input, in combination with those criteria: a good prompt describes what can be seen in the image in high detail. This should include what kind of image is requested (a photo, a drawing, etc.), what camera and lens was used (if a photo), the lighting and more. Only respond with the improved prompt, nothing else.'
                },{
                    'role': 'user',
                    'content': message.content
                }]

                # Send a request to GPT-4
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=messages,
                    max_tokens=3000,
                    n=1,
                    stop=None,
                    temperature=1,
                    top_p=1
                )

                # Extract the assistant's response from the API resultf
                assistant_response = response.choices[0].message['content']

                # Send the GPT-4 response in the Discord channel
                await ctx.send(assistant_response)
            except openai.error.RateLimitError as e:
                error_message = f"Error occurred: {type(e).__name__}: {str(e)}"
                await ctx.send(error_message)
            except Exception as e:
                print(f"Error occurred: {e}")
                traceback.print_exc()

    else:
        async with message.channel.typing():
            try:
                ctx = await bot.get_context(message)

                # Initialize conversation history and temperature if not already set
                if channel_name not in bot.conversations:
                    bot.conversations[channel_name] = [system_prompt_precise]
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
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=messages,
                    max_tokens=3000,
                    n=1,
                    stop=None,
                    temperature=ctx.bot.temperatures[channel_name],
                    top_p=1
                )

                # Extract the assistant's response from the API result
                assistant_response = response.choices[0].message['content']

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
            except openai.error.RateLimitError as e:
                error_message = f"Error occurred: {type(e).__name__}: {str(e)}"
                await ctx.send(error_message)
            except Exception as e:
                print(f"Error occurred: {e}")
                traceback.print_exc()

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
bot.run(DISCORD_BOT_TOKEN)
