import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("起動完了")

# コマンド読み込み
from commands.create import setup as create_setup
from commands.remind import setup as remind_setup

create_setup(bot)
remind_setup(bot)

bot.run(os.getenv("TOKEN"))
