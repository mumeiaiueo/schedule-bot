import os
import discord
import asyncpg
import pytz
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
JST = pytz.timezone("Asia/Tokyo")

# ===== 起動 =====
@bot.event
async def on_ready():
    bot.pool = await asyncpg.create_pool(DATABASE_URL)

    async with bot.pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS reserve(
            id SERIAL PRIMARY KEY,
            guild_id BIGINT,
            user_id BIGINT,
            start_at TIMESTAMP,
            end_at TIMESTAMP,
            notified BOOLEAN DEFAULT FALSE
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings(
            guild_id BIGINT PRIMARY KEY,
            notify_channel BIGINT
        );
        """)

    reminder.start()
    await tree.sync()
    print("起動完了")


# ⭐⭐⭐ ここに cleanup を置く ⭐⭐⭐
@tasks.loop(minutes=1)
async def cleanup():
    now = datetime.now(JST)

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
        DELETE FROM reserve
        WHERE end_at <= $1
        RETURNING *
        """, now)

        for r in rows:
            await conn.execute("""
            INSERT INTO reserve_history(guild_id,user_id,start_at,end_at)
            VALUES($1,$2,$3,$4)
            """, r["guild_id"], r["user_id"], r["start_at"], r["end_at"])


# ===== 通知チャンネル設定 =====
@tree.command(name="notifyset")
async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer()

    async with bot.pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO guild_settings(guild_id, notify_channel)
        VALUES($1,$2)
        ON CONFLICT(guild_id) DO UPDATE
        SET notify_channel=$2
        """, interaction.guild.id, channel.id)

    await interaction.followup.send("通知チャンネル設定完了")

# ===== 予約作成 =====

@tree.command(name="create")
@app_commands.describe(
    start="2026-02-22 23:00",
    end="2026-02-23 01:00",
    interval="分"
)
async def create(interaction: discord.Interaction, start: str, end: str, interval: int):

    await interaction.response.defer()

    try:
        start_dt = JST.localize(datetime.strptime(start, "%Y-%m-%d %H:%M"))
        end_dt = JST.localize(datetime.strptime(end, "%Y-%m-%d %H:%M"))
    except:
        await interaction.followup.send("時間形式エラー")
        return

    # ⭐ 日付またぎ
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    slots = []
    cur = start_dt

    while cur < end_dt:
        nxt = cur + timedelta(minutes=interval)
        slots.append((cur, nxt))
        cur = nxt

    async with bot.pool.acquire() as conn:
        for s, e in slots:
            await conn.execute("""
            INSERT INTO reserve(guild_id,start_at,end_at,user_id,notified)
            VALUES($1,$2,$3,NULL,false)
            """, interaction.guild.id, s, e)

        rows = await conn.fetch("""
        SELECT * FROM reserve
        WHERE guild_id=$1 AND user_id IS NULL
        """, interaction.guild.id)

    view = SlotView(rows)
    await interaction.followup.send("予約してください", view=view)

        if overlap:
            await interaction.followup.send("重複予約あり")
            return

        await conn.execute("""
        INSERT INTO reserve(guild_id,user_id,start_at,end_at)
        VALUES($1,$2,$3,$4)
        """, interaction.guild.id, interaction.user.id, start_dt, end_dt)

    await interaction.followup.send("予約完了")

class SlotButton(discord.ui.Button):
    def __init__(self, row):
        self.row = row

        if row["user_id"]:
            label = f"🔴 {row['start_at'].strftime('%H:%M')}"
            style = discord.ButtonStyle.danger
        else:
            label = f"🟢 {row['start_at'].strftime('%H:%M')}"
            style = discord.ButtonStyle.success

        super().__init__(label=label, style=style)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with bot.pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT * FROM reserve WHERE id=$1", self.row["id"]
            )

            # ⭐ 空き → 予約
            if not r["user_id"]:
                await conn.execute(
                    "UPDATE reserve SET user_id=$1 WHERE id=$2",
                    interaction.user.id, self.row["id"]
                )
                await interaction.followup.send("予約完了")

            # ⭐ 自分 → キャンセル
            elif r["user_id"] == interaction.user.id:
                await conn.execute(
                    "UPDATE reserve SET user_id=NULL WHERE id=$1",
                    self.row["id"]
                )
                await interaction.followup.send("キャンセルしました")

            # ⭐ 他人
            else:
                await interaction.followup.send("埋まっています")
                return

        # ⭐ UI更新
        new = await conn.fetchrow(
            "SELECT * FROM reserve WHERE id=$1", self.row["id"]
        )
        self.row = new

        if new["user_id"]:
            self.label = f"🔴 {new['start_at'].strftime('%H:%M')}"
            self.style = discord.ButtonStyle.danger
        else:
            self.label = f"🟢 {new['start_at'].strftime('%H:%M')}"
            self.style = discord.ButtonStyle.success

        await interaction.message.edit(view=self.view)

class SlotButton(discord.ui.Button):
    def __init__(self, row):
        self.row = row

        if row["user_id"]:
            label = f"🔴 {row['start_at'].strftime('%H:%M')}"
            style = discord.ButtonStyle.danger
        else:
            label = f"🟢 {row['start_at'].strftime('%H:%M')}"
            style = discord.ButtonStyle.success

        super().__init__(label=label, style=style)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        async with bot.pool.acquire() as conn:
            r = await conn.fetchrow(
                "SELECT * FROM reserve WHERE id=$1", self.row["id"]
            )

            # ⭐ 空き → 予約
            if not r["user_id"]:
                await conn.execute(
                    "UPDATE reserve SET user_id=$1 WHERE id=$2",
                    interaction.user.id, self.row["id"]
                )
                await interaction.followup.send("予約完了")

            # ⭐ 自分 → キャンセル
            elif r["user_id"] == interaction.user.id:
                await conn.execute(
                    "UPDATE reserve SET user_id=NULL WHERE id=$1",
                    self.row["id"]
                )
                await interaction.followup.send("キャンセルしました")

            # ⭐ 他人
            else:
                await interaction.followup.send("埋まっています")
                return

        # ⭐ UI更新
        new = await conn.fetchrow(
            "SELECT * FROM reserve WHERE id=$1", self.row["id"]
        )
        self.row = new

        if new["user_id"]:
            self.label = f"🔴 {new['start_at'].strftime('%H:%M')}"
            self.style = discord.ButtonStyle.danger
        else:
            self.label = f"🟢 {new['start_at'].strftime('%H:%M')}"
            self.style = discord.ButtonStyle.success

        await interaction.message.edit(view=self.view)

class SlotView(discord.ui.View):
    def __init__(self, rows):
        super().__init__(timeout=None)

        for r in rows:
            self.add_item(SlotButton(r))

# ===== 枠指定削除 =====
@tree.command(name="slotdelete", description="枠指定で削除（管理者）")
@app_commands.checks.has_permissions(administrator=True)
async def slotdelete(interaction: discord.Interaction, start: str):

    await interaction.response.defer(ephemeral=True)

    try:
        start_dt = JST.localize(datetime.strptime(start, "%Y-%m-%d %H:%M"))

    except:
        await interaction.followup.send("形式: 2026-02-22 18:00")
        return

    async with bot.pool.acquire() as conn:
        result = await conn.execute("""
        DELETE FROM reserve
        WHERE guild_id=$1
        AND start_at=$2
        """, interaction.guild.id, start_dt)

    if result == "DELETE 0":
        await interaction.followup.send("該当枠なし")
    else:
        await interaction.followup.send("削除完了")

# ===== 3分前通知 =====
@tasks.loop(minutes=1)
async def reminder():
    now = datetime.now(JST)

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT * FROM reserve
        WHERE notified=false
        AND start_at <= $1
        """, now + timedelta(minutes=3))

        for r in rows:
            channel_id = await conn.fetchval("""
            SELECT notify_channel FROM guild_settings
            WHERE guild_id=$1
            """, r["guild_id"])

            if channel_id:
                channel = bot.get_channel(channel_id)
                if channel:
                    await channel.send(f"<@{r['user_id']}> 3分前通知")

            await conn.execute("UPDATE reserve SET notified=true WHERE id=$1", r["id"])

bot.run(TOKEN)
