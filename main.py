import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"起動完了: {bot.user}")

# コマンド読み込み
from commands.create import setup as create_setup
from commands.settings import setup as settings_setup
from commands.remind import setup as remind_setup

create_setup(bot)
settings_setup(bot)
remind_setup(bot)

bot.run(TOKEN)
