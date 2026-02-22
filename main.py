import os
import discord
from discord.ext import commands

from utils.db import init_db_pool

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

class Bot(commands.Bot):
    async def setup_hook(self):
        if not TOKEN:
            raise RuntimeError("TOKEN が環境変数にありません")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL が環境変数にありません")

        # ⭐ DBプール作成 + テーブル作成
        self.pool = await init_db_pool(DATABASE_URL)
        print("✅ DB ready")

        # コマンド登録（今あるやつを順に）
        from commands.create import setup as create_setup
        create_setup(self)

        try:
            from commands.settings import setup as settings_setup
            settings_setup(self)
        except Exception as e:
            print("⚠ settings.py not loaded:", e)

        try:
            from commands.debug import setup as debug_setup
            debug_setup(self)
        except Exception as e:
            print("⚠ debug.py not loaded:", e)

        # リマインドは次のステップでDB版に差し替える（今日はまだOK）
        # from commands.remind import start_loop
        # await start_loop(self)

        await self.tree.sync()
        print("✅ commands synced")

intents = discord.Intents.default()
intents.message_content = False  # 公開用：基本OFF（スラッシュ運用）

bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("✅ on_ready:", bot.user)

bot.run(TOKEN)
