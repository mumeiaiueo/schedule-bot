import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import os

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("schedule.db")
c = conn.cursor()

# 予約テーブル
c.execute("""
CREATE TABLE IF NOT EXISTS schedule (
time TEXT,
user_id TEXT
)
""")

# 設定テーブル（ログチャンネル保存）
c.execute("""
CREATE TABLE IF NOT EXISTS config (
key TEXT,
value TEXT
)
""")

conn.commit()

last_channel_id = None

# ===== ログチャンネル取得 =====
def get_log_channel_id():
    c.execute("SELECT value FROM config WHERE key='log_channel'")
    row=c.fetchone()
    return int(row[0]) if row else None

# ===== ボタン =====
class TimeButton(discord.ui.Button):
    def __init__(self, time):
        super().__init__(label=time, style=discord.ButtonStyle.primary)
        self.time = time

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        c.execute("INSERT INTO schedule VALUES (?,?)",(self.time,user_id))
        conn.commit()

        self.label = f"{self.time} ({interaction.user.display_name})"
        self.style = discord.ButtonStyle.success
        await interaction.response.edit_message(view=self.view)

        # ===== ログ送信 =====
        log_id=get_log_channel_id()
        if log_id:
            log_channel=interaction.guild.get_channel(log_id)
            if log_channel:
                await log_channel.send(
                    f"{interaction.user.mention} が {self.time} を予約"
                )

# ===== View =====
class TimeView(discord.ui.View):
    def __init__(self, times):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(TimeButton(t))

# ===== 予約作成 =====
@bot.tree.command(name="schedule", description="予約作成")
@app_commands.describe(start="開始", end="終了", interval="間隔(分)")
async def schedule(interaction: discord.Interaction,start:str,end:str,interval:int):

    global last_channel_id
    last_channel_id = interaction.channel.id

    start_dt = datetime.strptime(start,"%H:%M")
    end_dt = datetime.strptime(end,"%H:%M")

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    times=[]
    while start_dt<=end_dt:
        times.append(start_dt.strftime("%H:%M"))
        start_dt += timedelta(minutes=interval)

    await interaction.response.send_message("予約してください",view=TimeView(times))

# ===== 予約一覧 =====
@bot.tree.command(name="list", description="予約一覧")
async def list_res(interaction: discord.Interaction):
    c.execute("SELECT time,user_id FROM schedule ORDER BY time")
    rows=c.fetchall()

    if not rows:
        await interaction.response.send_message("予約なし")
        return

    text=""
    for t,uid in rows:
        text+=f"{t} <@{uid}>\n"

    await interaction.response.send_message(text)

# ===== ログチャンネル設定（管理者のみ）=====
@bot.tree.command(name="setlog", description="ログチャンネル設定")
@app_commands.describe(channel="ログチャンネル")
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):

    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("管理者のみ設定可能",ephemeral=True)
        return

    c.execute("DELETE FROM config WHERE key='log_channel'")
    c.execute("INSERT INTO config VALUES (?,?)",("log_channel",str(channel.id)))
    conn.commit()

    await interaction.response.send_message(
        f"ログチャンネルを {channel.mention} に設定しました"
    )

# ===== 3分前通知 =====
@tasks.loop(seconds=30)
async def notify():
    now=(datetime.now()+timedelta(minutes=3)).strftime("%H:%M")

    c.execute("SELECT time,user_id FROM schedule WHERE time=?",(now,))
    rows=c.fetchall()

    if not rows:
        return

    log_id=get_log_channel_id()
    if not log_id:
        return

    channel=bot.get_channel(log_id)
    if not channel:
        return

    for t,uid in rows:
        await channel.send(f"<@{uid}> ⏰ {t} の3分前です！")

# ===== 起動 =====
@bot.event
async def on_ready():
    await bot.tree.sync()
    notify.start()
    print("ready")

bot.run(TOKEN)
