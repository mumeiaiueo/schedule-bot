import discord
from discord.ext import commands
from datetime import datetime, timedelta
import os

from views import SlotView
from storage import load, save
from tasks import start_tasks

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =====================
# 起動
# =====================
@bot.event
async def on_ready():

    # ⭐ 永続View復元
    data = load()
    for slot, v in data["reservations"].items():
        bot.add_view(SlotView(slot, v["end"]))

    start_tasks(bot)
    print(f"ログイン成功: {bot.user}")

# =====================
# 通知チャンネル設定
# =====================
@bot.command()
async def notifyset(ctx, channel: discord.TextChannel):

    data = load()
    data["notify"] = channel.id
    save(data)

    await ctx.send("✅ 通知チャンネル設定完了")

# =====================
# 枠生成コマンド
# =====================
@bot.command()
async def slots(ctx, start: str, end: str, interval: int):

    if interval not in [20,25,30]:
        await ctx.send("❌ 間隔は20・25・30")
        return

    try:
        start_time = datetime.strptime(start,"%H:%M")
        end_time = datetime.strptime(end,"%H:%M")
    except:
        await ctx.send("❌ 10:00形式")
        return

    current = start_time

    while current + timedelta(minutes=interval) <= end_time:

        next_time = current + timedelta(minutes=interval)

        slot = f"{current.strftime('%H:%M')}〜{next_time.strftime('%H:%M')}"

        view = SlotView(slot, next_time.strftime("%H:%M"))
        await ctx.send(f"🟢 {slot}", view=view)

        current = next_time

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
