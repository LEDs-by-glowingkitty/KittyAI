import os
import openai
import discord
from discord.ext import commands
from dotenv import load_dotenv
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

intents = discord.Intents.default()
intents.typing = False
intents.guilds = True
intents.messages = True
intents.presences = False
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

system_prompt = {"role": "system", "content": "You are a helpful assistant. Keep your answers as short and precise as possible."}


@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # if f'<@{bot.user.id}>' in message.content:
    message_history = [system_prompt]
    new_message = message.content.replace(f'<@{bot.user.id}>', '').strip()
    

    if message.channel.type.name == "text":
        # figure out what the thread is all about
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "system", "content": "You will receive a message from a user. Create a name for the thread."}, {"role": "user", "content": new_message}],
            max_tokens=200,
            n=1,
            stop=None,
            temperature=0,
            top_p=1
        )
        thread_name = response.choices[0].message['content']

        # send the message to gpt4 and get the response
        message_history.append({"role": "user", "content": new_message})
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=message_history,
            max_tokens=3000,
            n=1,
            stop=None,
            temperature=0,
            top_p=1
        )
        thread = await message.channel.create_thread(name=thread_name, message=message)
        await thread.send(response.choices[0].message['content'])
        
    else:
        
        async for msg in message.channel.history(oldest_first=True):
            if msg.type == discord.MessageType.thread_starter_message:
                thread_starter_message = msg.reference.resolved
                content = thread_starter_message.content.replace(f'<@{bot.user.id}>', '').strip()
                message_history.append({"role": "user", "content": content})
            else:
                content = content.replace(f'<@{bot.user.id}>', '').strip()
                message_history.append({"role": "user", "content": content})
        
        message_history.append({"role": "user", "content": new_message})
        
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=message_history,
            max_tokens=3000,
            n=1,
            stop=None,
            temperature=0,
            top_p=1
        )

        await message.channel.send(response.choices[0].message['content'])

    await bot.process_commands(message)

# Run the bot
def run_bot():
    bot.run(DISCORD_BOT_TOKEN)
    