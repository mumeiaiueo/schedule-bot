import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
from datetime import datetime, timedelta
import asyncio
import os

TOKEN = os.environ["TOKEN"]

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect("schedule.db")
c = conn.cursor()

# ===== DB =====
c.execute("""
CREATE TABLE IF NOT EXISTS schedule(
guild_id TEXT,
time TEXT,
user_id TEXT,
notified INTEGER DEFAULT 0,
PRIMARY KEY(guild_id,time)
)
""")

c.execute("""
CREATE TABLE IF NOT EXISTS config(
guild_id TEXT PRIMARY KEY,
log_channel TEXT,
panel_channel TEXT,
panel_message TEXT
)
""")
conn.commit()

guild_locks={}
notify_queue=asyncio.Queue()

# ===== LOCK =====
def get_lock(gid):
    if gid not in guild_locks:
        guild_locks[gid]=asyncio.Lock()
    return guild_locks[gid]

# ===== BUTTON =====
class TimeButton(discord.ui.Button):
    def __init__(self,time,gid):
        super().__init__(label=time,style=discord.ButtonStyle.primary)
        self.time=time
        self.gid=str(gid)

    async def callback(self,interaction:discord.Interaction):
        async with get_lock(self.gid):

            uid=str(interaction.user.id)

            c.execute("SELECT user_id FROM schedule WHERE guild_id=? AND time=?",(self.gid,self.time))
            row=c.fetchone()

            # ===== 予約 =====
            if not row:
                c.execute("INSERT INTO schedule VALUES (?,?,?,0)",(self.gid,self.time,uid))
                conn.commit()

                self.label=f"{self.time} ({interaction.user.display_name})"
                self.style=discord.ButtonStyle.success
                await interaction.response.edit_message(view=self.view)

                await send_log(self.gid,f"{interaction.user.mention} が {self.time} 予約")
                return

            # ===== 本人キャンセル =====
            if row[0]==uid:
                c.execute("DELETE FROM schedule WHERE guild_id=? AND time=?",(self.gid,self.time))
                conn.commit()

                self.label=self.time
                self.style=discord.ButtonStyle.primary
                await interaction.response.edit_message(view=self.view)

                await send_log(self.gid,f"{interaction.user.mention} が {self.time} キャンセル")
                return

            await interaction.response.send_message("埋まっています",ephemeral=True)

class TimeView(discord.ui.View):
    def __init__(self,times,gid):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(TimeButton(t,gid))

# ===== LOG =====
async def send_log(gid,msg):
    c.execute("SELECT log_channel FROM config WHERE guild_id=?",(gid,))
    row=c.fetchone()
    if not row or not row[0]:
        return
    ch=bot.get_channel(int(row[0]))
    if ch:
        await ch.send(msg)

# ===== COMMANDS =====
@bot.tree.command(name="schedule")
@app_commands.describe(start="開始",end="終了",interval="分")
async def schedule(interaction:discord.Interaction,start:str,end:str,interval:int):

    start_dt=datetime.strptime(start,"%H:%M")
    end_dt=datetime.strptime(end,"%H:%M")

    if end_dt<=start_dt:
        end_dt+=timedelta(days=1)

    times=[]
    while start_dt<=end_dt:
        times.append(start_dt.strftime("%H:%M"))
        start_dt+=timedelta(minutes=interval)

    msg=await interaction.response.send_message("予約",view=TimeView(times,interaction.guild.id))

    sent=await interaction.original_response()
    c.execute("INSERT OR REPLACE INTO config VALUES (?,?,?,?)",
              (str(interaction.guild.id),None,str(interaction.channel.id),str(sent.id)))
    conn.commit()

@bot.tree.command(name="setlog")
@app_commands.checks.has_permissions(administrator=True)
async def setlog(interaction:discord.Interaction,channel:discord.TextChannel):
    c.execute("INSERT OR REPLACE INTO config(guild_id,log_channel) VALUES(?,?)",
              (str(interaction.guild.id),str(channel.id)))
    conn.commit()
    await interaction.response.send_message("ログ設定OK")

@bot.tree.command(name="re")
async def re(interaction:discord.Interaction):
    c.execute("SELECT panel_channel,panel_message FROM config WHERE guild_id=?",(str(interaction.guild.id),))
    row=c.fetchone()
    if not row:
        await interaction.response.send_message("無し")
        return
    await interaction.response.send_message("復元OK")

# ===== NOTIFY WORKER =====
@tasks.loop(seconds=30)
async def notify_scan():
    now=(datetime.now()+timedelta(minutes=3)).strftime("%H:%M")
    c.execute("SELECT guild_id,time,user_id FROM schedule WHERE time=? AND notified=0",(now,))
    rows=c.fetchall()

    for gid,t,uid in rows:
        await notify_queue.put((gid,t,uid))
        c.execute("UPDATE schedule SET notified=1 WHERE guild_id=? AND time=?",(gid,t))
    conn.commit()

async def notify_worker():
    await bot.wait_until_ready()
    while True:
        gid,t,uid=await notify_queue.get()
        c.execute("SELECT log_channel FROM config WHERE guild_id=?",(gid,))
        row=c.fetchone()
        if row and row[0]:
            ch=bot.get_channel(int(row[0]))
            if ch:
                await ch.send(f"<@{uid}> ⏰ {t} の3分前")
        notify_queue.task_done()

# ===== AUTO DELETE + VACUUM =====
@tasks.loop(minutes=10)
async def cleanup():
    now=datetime.now().strftime("%H:%M")
    c.execute("DELETE FROM schedule WHERE time<?",(now,))
    conn.commit()
    c.execute("VACUUM")
    conn.commit()

# ===== READY =====
@bot.event
async def on_ready():
    await bot.tree.sync()
    bot.loop.create_task(notify_worker())
    notify_scan.start()
    cleanup.start()
    print("ready")

bot.run(TOKEN)
