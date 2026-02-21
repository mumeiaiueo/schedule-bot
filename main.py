import discord
from discord.ext import commands
from datetime import datetime, timedelta

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# 予約枠生成関数
def create_slots(start_str, end_str, interval):
    start = datetime.strptime(start_str, "%H:%M")
    end = datetime.strptime(end_str, "%H:%M")

    slots = []
    current = start

    while current + timedelta(minutes=interval) <= end:
        next_time = current + timedelta(minutes=interval)
        slots.append(f"{current.strftime('%H:%M')} - {next_time.strftime('%H:%M')}")
        current = next_time

    return slots


@bot.event
async def on_ready():
    print(f"ログイン完了: {bot.user}")


# コマンド
# 例: !枠 10:00 12:00 20
@bot.command()
async def 枠(ctx, start, end, interval: int):
    slots = create_slots(start, end, interval)

    if not slots:
        await ctx.send("枠が作れませんでした")
        return

    text = "\n".join(slots)
    await ctx.send(f"📅 予約枠\n{text}")


bot.run("TOKEN")
