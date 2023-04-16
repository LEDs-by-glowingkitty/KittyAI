import api_discord

# create a class for Kitty AI, which connects to all other functions (OpenAI API, Discord Bot, etc.)

class KittyAI:
    def start_discord_bot(self):
        # start the Discord bot
        api_discord.run_bot()

kittyAI = KittyAI()

kittyAI.start_discord_bot()