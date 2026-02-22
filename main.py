import discord
from discord.ext import commands
import os

# ⭐ 追加
from commands.create import setup as create_setup
from commands.remind import setup as remind_setup

create_setup(bot)
remind_setup(bot)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("起動完了")

# ⭐ コマンド読み込み
create_setup(bot)
remind_setup(bot)

# ⭐ リマインドループ起動
start_remind_loop(bot)

bot.run(os.getenv("TOKEN"))
