import discord
from discord.ext import commands
from datetime import datetime, timedelta
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"ログイン成功: {bot.user}")

# =====================
# 予約枠生成コマンド
# =====================
# 例:
# !slots 10:00 12:00 20
# =====================
@bot.command()
async def slots(ctx, start: str, end: str, interval: int):

    # 間隔チェック
    if interval not in [20, 25, 30]:
        await ctx.send("❌ 間隔は 20・25・30 のみ")
        return

    try:
        start_time = datetime.strptime(start, "%H:%M")
        end_time = datetime.strptime(end, "%H:%M")
    except:
        await ctx.send("❌ 時刻は 10:00 の形式で入力")
        return

    if start_time >= end_time:
        await ctx.send("❌ 終了は開始より後")
        return

    # 枠生成
    slots = []
    current = start_time

    while current + timedelta(minutes=interval) <= end_time:
        next_time = current + timedelta(minutes=interval)
        slots.append(f"{current.strftime('%H:%M')}〜{next_time.strftime('%H:%M')}")
        current = next_time

    # 表示
    msg = "📅 予約枠\n"
    for s in slots:
        msg += f"🟢 {s}\n"

    await ctx.send(msg)

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
