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

# ===== DB =====
conn = sqlite3.connect("schedule.db")
c = conn.cursor()
c.execute("CREATE TABLE IF NOT EXISTS reservations(time TEXT PRIMARY KEY, user_id TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS logs(action TEXT, time TEXT, user_id TEXT, date TEXT)")
conn.commit()

# ===== 自動削除 =====
@tasks.loop(minutes=1)
async def auto_delete():
    now = datetime.now().strftime("%H:%M")
    c.execute("DELETE FROM reservations WHERE time<?", (now,))
    conn.commit()

# ===== ボタン =====
class ReserveButton(discord.ui.Button):
    def __init__(self, time, row):
        c.execute("SELECT user_id FROM reservations WHERE time=?", (time,))
        data = c.fetchone()

        if data:
            user = bot.get_user(int(data[0]))
            label = f"{time} {user.name if user else '予約'}"
            style = discord.ButtonStyle.gray
            disabled = False
        else:
            label = time
            style = discord.ButtonStyle.green
            disabled = False

        super().__init__(label=label, style=style, disabled=disabled, row=row)
        self.time = time

    async def callback(self, interaction: discord.Interaction):
        c.execute("SELECT user_id FROM reservations WHERE time=?", (self.time,))
        data = c.fetchone()

        # ===== 既予約 =====
        if data:
            # 本人 or 管理者なら変更
            if str(interaction.user.id) == data[0] or interaction.user.guild_permissions.administrator:
                c.execute("DELETE FROM reservations WHERE time=?", (self.time,))
                conn.commit()

                c.execute("INSERT INTO logs VALUES (?,?,?,?)",
                          ("cancel", self.time, str(interaction.user.id), str(datetime.now())))
                conn.commit()

                self.label = self.time
                self.style = discord.ButtonStyle.green
                await interaction.response.edit_message(view=self.view)
                await interaction.followup.send("キャンセルしました", ephemeral=True)
            else:
                await interaction.response.send_message("予約済み", ephemeral=True)
            return

        # ===== 新規予約 =====
        c.execute("INSERT INTO reservations VALUES (?,?)", (self.time, str(interaction.user.id)))
        conn.commit()

        c.execute("INSERT INTO logs VALUES (?,?,?,?)",
                  ("reserve", self.time, str(interaction.user.id), str(datetime.now())))
        conn.commit()

        self.label = f"{self.time} {interaction.user.name}"
        self.style = discord.ButtonStyle.gray

        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send(f"{interaction.user.mention} が {self.time} 予約")

# ===== ページ送り =====
class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="▶", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        view = ReserveView(self.view.times, self.view.page + 1)
        await interaction.response.edit_message(view=view)

class PrevButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀", style=discord.ButtonStyle.blurple)

    async def callback(self, interaction: discord.Interaction):
        view = ReserveView(self.view.times, self.view.page - 1)
        await interaction.response.edit_message(view=view)

# ===== View =====
class ReserveView(discord.ui.View):
    def __init__(self, times, page=0):
        super().__init__(timeout=None)
        self.times = times
        self.page = page

        start = page * 5
        end = start + 5
        page_times = times[start:end]

        row = 0
        for t in page_times:
            self.add_item(ReserveButton(t, row))
            row += 1

        if page > 0:
            self.add_item(PrevButton())

        if end < len(times):
            self.add_item(NextButton())

# ===== schedule =====
@bot.tree.command(name="schedule")
async def schedule(interaction: discord.Interaction, start: str, end: str, interval: int):
    s = datetime.strptime(start, "%H:%M")
    e = datetime.strptime(end, "%H:%M")

    if e <= s:
        e += timedelta(days=1)

    times = []
    while s <= e:
        times.append(s.strftime("%H:%M"))
        s += timedelta(minutes=interval)

    await interaction.response.send_message("予約してください", view=ReserveView(times))

# ===== 予約一覧 =====
@bot.tree.command(name="予約一覧")
async def list_reserve(interaction: discord.Interaction):
    c.execute("SELECT * FROM reservations ORDER BY time")
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("予約なし")
        return

    msg = ""
    for t, u in rows:
        user = await bot.fetch_user(int(u))
        msg += f"{t} {user.name}\n"

    await interaction.response.send_message(msg)

# ===== 履歴 =====
@bot.tree.command(name="履歴")
async def history(interaction: discord.Interaction):
    c.execute("SELECT * FROM logs ORDER BY date DESC LIMIT 20")
    rows = c.fetchall()

    if not rows:
        await interaction.response.send_message("履歴なし")
        return

    msg = ""
    for a, t, u, d in rows:
        user = await bot.fetch_user(int(u))
        msg += f"{a} {t} {user.name} {d}\n"

    await interaction.response.send_message(msg)

# ===== 強制予約 =====
@bot.tree.command(name="強制予約")
async def force(interaction: discord.Interaction, time: str, user: discord.Member):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者のみ", ephemeral=True)
        return

    c.execute("INSERT OR REPLACE INTO reservations VALUES (?,?)", (time, str(user.id)))
    conn.commit()
    await interaction.response.send_message("強制予約完了")

# ===== 起動 =====
@bot.event
async def on_ready():
    await bot.tree.sync()
    auto_delete.start()
    print("起動")

bot.run(TOKEN)
