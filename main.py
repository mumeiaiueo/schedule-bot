import os
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ===== 起動 =====
@bot.event
async def on_ready():
    await tree.sync()
    print("起動完了")

# ===== 予約枠生成 =====
@tree.command(name="create", description="予約枠生成")
@app_commands.describe(
    start="開始 HH:MM",
    end="終了 HH:MM",
    interval="間隔選択"
)
@app_commands.choices(interval=[
    app_commands.Choice(name="20分", value=20),
    app_commands.Choice(name="25分", value=25),
    app_commands.Choice(name="30分", value=30),
])
async def create(
    interaction: discord.Interaction,
    start: str,
    end: str,
    interval: app_commands.Choice[int]
):
    await interaction.response.defer()

    try:
        start_dt = datetime.strptime(start, "%H:%M")
        end_dt = datetime.strptime(end, "%H:%M")
    except:
        await interaction.followup.send("❌ HH:MM形式で入力")
        return

    if start_dt >= end_dt:
        await interaction.followup.send("❌ 終了は開始より後")
        return

    i = interval.value

    slots = []
    current = start_dt

    while current + timedelta(minutes=i) <= end_dt:
        nxt = current + timedelta(minutes=i)
        slots.append(f"{current.strftime('%H:%M')}〜{nxt.strftime('%H:%M')}")
        current = nxt

@tree.command(name="create")
async def create(interaction: discord.Interaction, start: str, end: str, interval: int):

    slots = make_slots(start, end, interval)

    msg = "📅 予約枠\n"
    for s in slots:
        msg += f"🟢 {s}\n"

    await interaction.response.send_message(msg, view=SlotView(slots))
