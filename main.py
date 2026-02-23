import os
import asyncio
import logging
import traceback

import discord
from discord.ext import commands

from utils.db import init_db_pool

# ===== ログ（落ちた理由を必ず出す）=====
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("schedule-bot")

TOKEN = os.getenv("TOKEN")  # RenderのEnvironmentで TOKEN
DATABASE_URL = os.getenv("DATABASE_URL")  # RenderのEnvironmentで DATABASE_URL


class Bot(commands.Bot):
    def sid(self, x) -> str:
        """DiscordのID(int)をDB用の文字列に統一"""
        return str(x) if x is not None else None

    async def setup_hook(self):
        log.info("🚀 setup_hook start")

        # 環境変数チェック（値は出さない）
        if not TOKEN:
            raise RuntimeError("TOKEN が環境変数にありません")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL が環境変数にありません")

        # DB接続
        self.pool = await init_db_pool(DATABASE_URL)
        log.info("✅ DB ready")

        # コマンド登録
        from commands.create import setup as create_setup
        create_setup(self)

        try:
            from commands.settings import setup as settings_setup
            settings_setup(self)
        except Exception as e:
            log.warning("⚠ settings.py not loaded: %s", e)

        try:
            from commands.debug import setup as debug_setup
            debug_setup(self)
        except Exception as e:
            log.warning("⚠ debug.py not loaded: %s", e)

        # remind 起動（落ちてもbot全体は落とさない）
        try:
            from commands.remind import start_remind
            start_remind(self)
            log.info("✅ remind started")
        except Exception as e:
            log.error("⚠ remind 起動失敗: %s", e)
            traceback.print_exc()

        # コマンド同期（ここで落ちることもあるのでログ）
        await self.tree.sync()
        log.info("✅ commands synced")

        log.info("🚀 setup_hook end")


intents = discord.Intents.default()
intents.message_content = False  # スラッシュ運用なら不要（WARNINGは出るが致命的ではない）

bot = Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("✅ on_ready: %s", bot.user)


async def runner():
    """
    ここがポイント：
    - 例外で落ちても、原因をログに出して少し待って再接続する
    - Renderの「即再起動ループ」よりデバッグしやすい
    """
    while True:
        try:
            log.info("🔌 bot starting...")
            await bot.start(TOKEN, reconnect=True)
        except Exception as e:
            log.error("💥 bot crashed: %s", e)
            traceback.print_exc()
            try:
                # DBプールを閉じる（存在する場合）
                if hasattr(bot, "pool") and bot.pool is not None:
                    await bot.pool.close()
                    log.info("✅ DB pool closed")
            except Exception:
                traceback.print_exc()

            log.info("⏳ restarting in 10 seconds...")
            await asyncio.sleep(10)
        else:
            # bot.start が普通に返るのは stop/close されたとき
            log.warning("bot.start returned; restarting in 10 seconds...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    asyncio.run(runner())