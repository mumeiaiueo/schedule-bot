import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# コマンド読み込み
from commands.create import setup as create_setup
from commands.remind import setup as remind_setup, start_remind_loop

create_setup(bot)
remind_setup(bot)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("起動完了")

    # ⭐ これが超重要（通知ループ起動）
    start_remind_loop(bot)

bot.run(os.getenv("TOKEN"))
