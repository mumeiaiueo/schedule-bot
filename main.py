# main.py
import os
import asyncio
import logging
import traceback

import discord
from discord.ext import commands

from utils.db import init_db_pool

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("schedule-bot")

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")


class Bot(commands.Bot):
    async def setup_hook(self):
        log.info("🚀 setup_hook start")

        if not TOKEN:
            raise RuntimeError("TOKEN が環境変数にありません")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL が環境変数にありません")

        # DB
        self.pool = await init_db_pool(DATABASE_URL)
        log.info("✅ DB ready")

        # コマンド読み込み（落ちても bot 自体は起動させる）
        def safe_load(name: str, fn):
            try:
                fn()
                log.info(f"✅ loaded: {name}")
            except Exception:
                log.error(f"💥 load failed: {name}")
                traceback.print_exc()

        safe_load("setup_channel", lambda: __import__("commands.setup_channel", fromlist=["setup"]).setup(self))
        safe_load("reset_channel", lambda: __import__("commands.reset_channel", fromlist=["setup"]).setup(self))
        safe_load("remind_channel", lambda: __import__("commands.remind_channel", fromlist=["start_remind_channel"]).start_remind_channel(self))

        await self.tree.sync()
        log.info("✅ commands synced")
        log.info("🚀 setup_hook end")


intents = discord.Intents.default()
intents.message_content = False
bot = Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("✅ on_ready: %s", bot.user)


async def runner():
    backoff = 30
    while True:
        try:
            log.info("🔌 bot starting...")
            await bot.start(TOKEN, reconnect=True)

            log.warning("bot.start returned; restarting later...")
            await asyncio.sleep(backoff)

        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()

            try:
                if getattr(bot, "pool", None) is not None:
                    await bot.pool.close()
                    log.info("✅ DB pool closed")
            except Exception:
                traceback.print_exc()

            log.info("⏳ restarting in %s seconds...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 600)

        else:
            backoff = 30


if __name__ == "__main__":
    asyncio.run(runner())