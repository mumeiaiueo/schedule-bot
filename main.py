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

    await tree.sync()
    print("起動完了")

# ===== 枠生成（STEP1）=====
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

    cur = start_dt
    created = 0

    async with bot.pool.acquire() as conn:
        while cur < end_dt:
            nxt = cur + timedelta(minutes=interval)

            await conn.execute("""
            INSERT INTO reserve(guild_id,user_id,start_at,end_at)
            VALUES($1,NULL,$2,$3)
            """, interaction.guild.id, cur, nxt)

            created += 1
            cur = nxt

    await interaction.followup.send(f"枠生成完了 ({created}枠)")

bot.run(TOKEN)
