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

        self.pool = await init_db_pool(DATABASE_URL)
        log.info("✅ DB ready")

        def safe_load(name, fn):
            try:
                fn()
                log.info(f"✅ loaded: {name}")
            except Exception:
                log.error(f"❌ load failed: {name}")
                traceback.print_exc()

        from commands.setup_channel import setup as setup_channel_setup
        safe_load("setup_channel", lambda: setup_channel_setup(self))

        from commands.reset_channel import setup as reset_channel_setup
        safe_load("reset_channel", lambda: reset_channel_setup(self))

        from commands.remind_channel import start_remind_channel
        safe_load("remind_channel", lambda: start_remind_channel(self))

        await self.tree.sync()
        log.info("✅ commands synced")


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

        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()

            try:
                if getattr(bot, "pool", None):
                    await bot.pool.close()
            except Exception:
                traceback.print_exc()

            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 600)


if __name__ == "__main__":
    asyncio.run(runner())