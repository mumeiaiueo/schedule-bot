import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta

TOKEN = "YOUR_TOKEN"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ===== DB =====
conn = sqlite3.connect("schedule.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS slots (time TEXT PRIMARY KEY, user_id TEXT, name TEXT)")
conn.commit()

# ===== ボタン =====
class SlotButton(discord.ui.Button):
    def __init__(self, time):
        c.execute("SELECT name FROM slots WHERE time=?", (time,))
        row = c.fetchone()

        if row:
            label = f"予約済 {time} ({row[0]})"
            style = discord.ButtonStyle.danger
        else:
            label = f"空き {time}"
            style = discord.ButtonStyle.success

        super().__init__(label=label, style=style)
        self.time = time

    async def callback(self, interaction: discord.Interaction):
        c.execute("SELECT user_id FROM slots WHERE time=?", (self.time,))
        row = c.fetchone()

        # ===== 解除 =====
        if row and row[0] == str(interaction.user.id):
            c.execute("DELETE FROM slots WHERE time=?", (self.time,))
            conn.commit()

            self.label = f"空き {self.time}"
            self.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send(f"❌ {interaction.user.mention} が {self.time} をキャンセル")
            return

        # ===== 他人予約済 =====
        if row:
            await interaction.response.send_message("❌ すでに予約済み", ephemeral=True)
            return

        # ===== 予約 =====
        c.execute(
            "INSERT INTO slots VALUES (?,?,?)",
            (self.time, str(interaction.user.id), interaction.user.display_name),
        )
        conn.commit()

        self.label = f"予約済 {self.time} ({interaction.user.display_name})"
        self.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"✅ {interaction.user.mention} が {self.time} を予約しました")


# ===== View（1列表示）=====
class SlotView(discord.ui.View):
    def __init__(self, times):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(SlotButton(t))


# ===== スケジュール作成 =====
@bot.tree.command(name="schedule")
@app_commands.checks.has_permissions(administrator=True)
async def schedule(interaction: discord.Interaction, start: str, end: str, interval: int):

    fmt = "%H:%M"
    s = datetime.strptime(start, fmt)
    e = datetime.strptime(end, fmt)

    # 日跨ぎ対応
    if e < s:
        e += timedelta(days=1)

    times = []
    while s <= e:
        times.append(s.strftime(fmt))
        s += timedelta(minutes=interval)

    await interaction.response.send_message("予約してください", view=SlotView(times))


# ===== 予約一覧 =====
@bot.tree.command(name="list")
async def list_slots(interaction: discord.Interaction):
    c.execute("SELECT time,name FROM slots ORDER BY time")
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("予約なし")
        return

    text = "\n".join([f"{r[0]} → {r[1]}" for r in rows])
    await interaction.response.send_message(text)


# ===== 管理者のみ全削除 =====
@bot.tree.command(name="reset")
@app_commands.checks.has_permissions(administrator=True)
async def reset(interaction: discord.Interaction):
    c.execute("DELETE FROM slots")
    conn.commit()
    await interaction.response.send_message("✅ すべての予約を削除しました")




@bot.event
async def on_ready():
    await bot.tree.sync()
    print("ready")

from discord.ext import tasks

notified = set()

@tasks.loop(seconds=30)
async def reminder():
    now = datetime.now()
    target = (now + timedelta(minutes=3)).strftime("%H:%M")

    c.execute("SELECT time,user_id FROM slots")
    rows = c.fetchall()

    for t, uid in rows:
        if t == target and t not in notified:
            channel = bot.get_channel(last_channel_id)
            if channel:
                await channel.send(f"<@{uid}> ⏰ {t} の3分前です！")
            notified.add(t)

bot.run(TOKEN)
