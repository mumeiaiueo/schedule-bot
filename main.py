import os
import discord
from discord.ext import commands

from utils.db import init_db_pool

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
GUILD_ID = os.getenv("GUILD_ID")  # ← 任意（入れると反映が速い）

class Bot(commands.Bot):
    async def setup_hook(self):
        print("🚀 setup_hook start")

        if not TOKEN:
            raise RuntimeError("TOKEN が環境変数にありません")
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL が環境変数にありません")

        # DB
        self.pool = await init_db_pool(DATABASE_URL)
        print("✅ DB ready")

        # コマンド（一本化：create のみ）
        from commands.create import setup as create_setup
        create_setup(self)

        # ❌ /notifyset を消すため、settings は読み込まない
        # from commands.settings import setup as settings_setup
        # settings_setup(self)

        # ❌ 競合しやすいので debug も一旦読み込まない（必要なら後で戻す）
        # from commands.debug import setup as debug_setup
        # debug_setup(self)

        # remind
        try:
            from commands.remind import start_remind
            start_remind(self)
            print("✅ remind started")
        except Exception as e:
            print("⚠ remind 起動失敗:", e)

        # コマンド同期（ギルド優先）
        if GUILD_ID:
            guild = discord.Object(id=int(GUILD_ID))
            await self.tree.sync(guild=guild)
            print("✅ commands synced (guild)")
        else:
            await self.tree.sync()
            print("✅ commands synced (global)")

        print("🏁 setup_hook end")

intents = discord.Intents.default()
intents.message_content = False

bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("✅ on_ready:", bot.user)

bot.run(TOKEN)