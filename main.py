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


def safe_setup(name: str, fn):
    try:
        fn()
        log.info("✅ loaded: %s", name)
        return True
    except Exception as e:
        log.error("❌ load failed: %s (%s: %s)", name, type(e).__name__, e)
        traceback.print_exc()
        return False


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

        # コマンド読み込み（失敗してもBotは落とさない）
        def load_commands():
            from commands.setup_channel import setup as setup_channel_setup
            setup_channel_setup(self)

            from commands.reset_channel import setup as reset_channel_setup
            reset_channel_setup(self)

            from commands.remind_channel import start_remind_channel
            start_remind_channel(self)

        safe_setup("commands", load_commands)

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
    backoff = 60
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
            backoff = 60


if __name__ == "__main__":
    asyncio.run(runner())