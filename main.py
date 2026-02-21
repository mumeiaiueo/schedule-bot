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
async def create(interaction: discord.Interaction, start: str, end: str):
    await interaction.response.defer()

    start_dt = JST.localize(datetime.strptime(start, "%Y-%m-%d %H:%M"))
    end_dt = JST.localize(datetime.strptime(end, "%Y-%m-%d %H:%M"))

    async with bot.pool.acquire() as conn:
        overlap = await conn.fetchrow("""
        SELECT * FROM reserve
        WHERE guild_id=$1
        AND NOT ($3 <= start_at OR $2 >= end_at)
        """, interaction.guild.id, start_dt, end_dt)

        if overlap:
            await interaction.followup.send("重複予約あり")
            return

        await conn.execute("""
        INSERT INTO reserve(guild_id,user_id,start_at,end_at)
        VALUES($1,$2,$3,$4)
        """, interaction.guild.id, interaction.user.id, start_dt, end_dt)

    await interaction.followup.send("予約完了")

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
