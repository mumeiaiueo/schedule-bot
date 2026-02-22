import discord
from discord.ext import commands
import os
from notify import start_tasks
from storage import load, save

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def setup_hook():
    await bot.load_extension("slots")

@bot.command()
async def notifyset(ctx, channel: discord.TextChannel):
    data = load()
    data["notify"][str(ctx.guild.id)] = channel.id
    save(data)
    await ctx.send("通知チャンネル設定完了")

@bot.event
async def on_ready():
    start_tasks(bot)
    print(f"ログイン成功: {bot.user}")

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
