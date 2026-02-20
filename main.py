import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import os
TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("schedule.db")
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS slots
(time TEXT PRIMARY KEY, user_id TEXT)""")
conn.commit()

class SlotButton(discord.ui.Button):
    def __init__(self, time):
        super().__init__(label=time, style=discord.ButtonStyle.primary)
        self.time = time

    async def callback(self, interaction: discord.Interaction):
        c.execute("SELECT user_id FROM slots WHERE time=?", (self.time,))
        row = c.fetchone()

        if row is None:
            c.execute("INSERT INTO slots VALUES (?,?)", (self.time, str(interaction.user.id)))
            conn.commit()
            await interaction.response.send_message(f"{self.time} を予約しました", ephemeral=True)

        elif row[0] == str(interaction.user.id):
            c.execute("DELETE FROM slots WHERE time=?", (self.time,))
            conn.commit()
            await interaction.response.send_message(f"{self.time} をキャンセルしました", ephemeral=True)

        else:
            await interaction.response.send_message("すでに予約済み", ephemeral=True)

class SlotView(discord.ui.View):
    def __init__(self, times):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(SlotButton(t))

@bot.tree.command(name="schedule")
@app_commands.checks.has_permissions(administrator=True)
async def schedule(interaction: discord.Interaction, start: str, end: str, interval: int):
    fmt = "%H:%M"
    s = datetime.strptime(start, fmt)
    e = datetime.strptime(end, fmt)

    times = []
    while s <= e:
        times.append(s.strftime(fmt))
        s += timedelta(minutes=interval)

    await interaction.response.send_message("予約してください", view=SlotView(times))

@tasks.loop(seconds=30)
async def reminder():
    now = datetime.now().strftime("%H:%M")
    target = (datetime.now()+timedelta(minutes=3)).strftime("%H:%M")

    c.execute("SELECT user_id FROM slots WHERE time=?", (target,))
    rows = c.fetchall()
    for r in rows:
        user = await bot.fetch_user(int(r[0]))
        try:
            await user.send(f"{target} の3分前です！")
        except:
            pass

@bot.event
async def on_ready():
    await bot.tree.sync()
    reminder.start()
    print("ready")

bot.run(TOKEN)
