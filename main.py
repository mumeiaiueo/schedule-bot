import os
import discord
import asyncpg
import pytz
from discord.ext import commands, tasks
from discord import app_commands
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

# ===== 予約枠生成（間隔付き）=====
@tree.command(name="create")
@app_commands.describe(
    start="開始 2026-02-22 18:00",
    end="終了 2026-02-22 23:00",
    interval="20 / 25 / 30"
)
async def create(
    interaction: discord.Interaction,
    start: str,
    end: str,
    interval: int
):
    await interaction.response.defer()

    if interval not in [20, 25, 30]:
        await interaction.followup.send("間隔は 20 / 25 / 30 のみ")
        return

    try:
        start_dt = JST.localize(datetime.strptime(start, "%Y-%m-%d %H:%M"))
        end_dt = JST.localize(datetime.strptime(end, "%Y-%m-%d %H:%M"))
    except:
        await interaction.followup.send("形式: 2026-02-22 18:00")
        return

    # ⭐ 日付またぎ
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    created = 0
    cur = start_dt

    async with bot.pool.acquire() as conn:
        while cur < end_dt:
            nxt = cur + timedelta(minutes=interval)

            overlap = await conn.fetchrow("""
            SELECT 1 FROM reserve
            WHERE guild_id=$1
            AND NOT ($3 <= start_at OR $2 >= end_at)
            """, interaction.guild.id, cur, nxt)

            if not overlap:
                await conn.execute("""
                INSERT INTO reserve(guild_id,user_id,start_at,end_at)
                VALUES($1,NULL,$2,$3)
                """, interaction.guild.id, cur, nxt)
                created += 1

            cur = nxt

    await interaction.followup.send(f"枠生成完了 ({created}枠)")

# ===== 3分前通知 =====
@tasks.loop(minutes=1)
async def reminder():
    now = datetime.now(JST)

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT * FROM reserve
        WHERE notified=false
        AND user_id IS NOT NULL
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

            await conn.execute(
                "UPDATE reserve SET notified=true WHERE id=$1",
                r["id"]
            )

bot.run(TOKEN)
