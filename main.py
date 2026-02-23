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
        except Exception as e:
            log.error("💥 setup_channel load failed: %s", e)
            traceback.print_exc()

        try:
            from commands.reset_channel import setup as reset_channel_setup
            reset_channel_setup(self)
            log.info("✅ reset_channel loaded")
        except Exception as e:
            log.error("💥 reset_channel load failed: %s", e)
            traceback.print_exc()

        # =============================
        # チャンネル専用remind起動
        # =============================
        try:
            from commands.remind_channel import start_remind_channel
            start_remind_channel(self)
            log.info("✅ remind_channel started")
        except Exception as e:
            log.error("💥 remind_channel start failed: %s", e)
            traceback.print_exc()

        # コマンド同期（※頻繁に落ちるなら rate limit になるので注意）
        await self.tree.sync()
        log.info("✅ commands synced")

        log.info("🚀 setup_hook end")


def make_bot() -> Bot:
    intents = discord.Intents.default()
    intents.message_content = False
    return Bot(command_prefix="!", intents=intents)


async def runner():
    while True:
        bot = make_bot()

        @bot.event
        async def on_ready():
            log.info("✅ on_ready: %s", bot.user)

        try:
            log.info("🔌 bot starting...")
            await bot.start(TOKEN)

            # bot.start が普通に戻るのは stop/close された時だけ
            log.warning("bot.start returned; restarting in 60 seconds...")
            await asyncio.sleep(60)

        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()

            # DBプールを閉じる
            try:
                if hasattr(bot, "pool") and bot.pool is not None:
                    await bot.pool.close()
                    log.info("✅ DB pool closed")
            except Exception:
                traceback.print_exc()

            # botも閉じる（中途半端接続の残りを防ぐ）
            try:
                await bot.close()
            except Exception:
                pass

            log.info("⏳ restarting in 60 seconds...")
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(runner())