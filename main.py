import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

class Bot(commands.Bot):
    async def setup_hook(self):
        from commands.remind import start_loop
        await start_loop(self)

intents = discord.Intents.default()
intents.message_content = True   # ←追加

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("起動完了:", bot.user)

from commands.create import setup as create_setup
from commands.settings import setup as settings_setup
from commands.debug import setup as debug_setup

create_setup(bot)
settings_setup(bot)
debug_setup(bot)

bot.run(TOKEN)
