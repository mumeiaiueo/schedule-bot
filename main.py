import os
import discord
from discord.ext import commands

from utils.db import init_db_pool

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

class Bot(commands.Bot):

    async def setup_hook(self):
        print("🚀 setup_hook start")

        if not TOKEN:
            raise RuntimeError("TOKEN が環境変数にありません")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL が環境変数にありません")

        print("📦 DB初期化開始")
        self.pool = await init_db_pool(DATABASE_URL)
        print("✅ DB ready")

        print("📦 コマンド読み込み開始")
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

        print("📦 remind読み込み開始")
        try:
            from commands.remind import start_remind
            start_remind(self)
            print("🔥 remind 起動処理呼び出し完了")
        except Exception as e:
            print("⚠ remind 起動失敗:", e)

        await self.tree.sync()
        print("✅ commands synced")
        print("🚀 setup_hook end")

intents = discord.Intents.default()
intents.message_content = False

bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("✅ on_ready:", bot.user)

bot.run(TOKEN)