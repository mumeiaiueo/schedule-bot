import os
import asyncio
import logging
import traceback

import discord
from discord.ext import commands

from utils.db import init_db_pool

# ===== ログ =====
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

        # DB接続
        self.pool = await init_db_pool(DATABASE_URL)
        log.info("✅ DB ready")

        # =============================
        # 新設計コマンド登録
        # =============================
        try:
            from commands.setup_channel import setup as setup_channel_setup
            setup_channel_setup(self)
            log.info("✅ setup_channel loaded")
        except Exception:
            traceback.print_exc()

        try:
            from commands.reset_channel import setup as reset_channel_setup
            reset_channel_setup(self)
            log.info("✅ reset_channel loaded")
        except Exception:
            traceback.print_exc()

        # =============================
        # チャンネル専用remind起動
        # =============================
        try:
            from commands.remind_channel import start_remind_channel
            start_remind_channel(self)
            log.info("✅ remind_channel started")
        except Exception:
            traceback.print_exc()

        # コマンド同期
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
    while True:
        try:
            log.info("🔌 bot starting...")
            await bot.start(TOKEN)
        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()

            try:
                if hasattr(bot, "pool") and bot.pool is not None:
                    await bot.pool.close()
                    log.info("✅ DB pool closed")
            except Exception:
                traceback.print_exc()

            log.info("⏳ restarting in 10 seconds...")
            await asyncio.sleep(60)
        else:
            log.warning("bot.start returned; restarting in 10 seconds...")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(runner())