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


def make_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = False  # スラッシュ運用なら不要

    class Bot(commands.Bot):
        async def setup_hook(self):
            log.info("🚀 setup_hook start")

            token = os.getenv("TOKEN")
            database_url = os.getenv("DATABASE_URL")

            if not token:
                raise RuntimeError("TOKEN が環境変数にありません")
            if not database_url:
                raise RuntimeError("DATABASE_URL が環境変数にありません")

            # DB接続
            self.pool = await init_db_pool(database_url)
            log.info("✅ DB ready")

            # コマンド登録（落ちても原因ログが出るように個別try）
            try:
                from commands.setup_channel import setup as setup_channel_setup
                setup_channel_setup(self)
                log.info("✅ setup_channel loaded")
            except Exception:
                log.error("💥 setup_channel load failed")
                traceback.print_exc()
                raise

            try:
                from commands.reset_channel import setup as reset_channel_setup
                reset_channel_setup(self)
                log.info("✅ reset_channel loaded")
            except Exception:
                log.error("💥 reset_channel load failed")
                traceback.print_exc()
                raise

            # remind 起動
            try:
                from commands.remind_channel import start_remind_channel
                start_remind_channel(self)
                log.info("✅ remind_channel started")
            except Exception:
                log.error("💥 remind_channel start failed")
                traceback.print_exc()
                raise

            # コマンド同期
            await self.tree.sync()
            log.info("✅ commands synced")
            log.info("🚀 setup_hook end")

    bot = Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        log.info("✅ on_ready: %s", bot.user)

    return bot


async def runner():
    backoff = 60  # 60→120→240→480→600
    while True:
        bot = make_bot()
        token = os.getenv("TOKEN")

        try:
            log.info("🔌 bot starting...")
            await bot.start(token, reconnect=True)

            # 普通はここに来ない（stop/closeされた時だけ）
            log.warning("bot.start returned; restarting later...")
            await asyncio.sleep(backoff)
            backoff = 60

        except asyncio.CancelledError:
            # Render停止など
            log.warning("⛔ cancelled")
            try:
                await bot.close()
            except Exception:
                pass
            raise

        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()

            # DBプールを閉じる
            try:
                pool = getattr(bot, "pool", None)
                if pool is not None:
                    await pool.close()
                    log.info("✅ DB pool closed")
            except Exception:
                traceback.print_exc()

            # bot も明示的に閉じる
            try:
                await bot.close()
            except Exception:
                pass

            log.info("⏳ restarting in %s seconds...", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 600)


if __name__ == "__main__":
    asyncio.run(runner())