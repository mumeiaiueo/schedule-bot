import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")

class Bot(commands.Bot):
    async def setup_hook(self):
        print("✅ setup_hook start")

        from commands.create import setup as create_setup
        create_setup(self)

        # notifyset が別ファイルならここで読み込み
        try:
            from commands.settings import setup as settings_setup
            settings_setup(self)
        except Exception as e:
            print("⚠ settings.py not loaded:", e)

        # debug（/debugdata /pingnotify）
        try:
            from commands.debug import setup as debug_setup
            debug_setup(self)
        except Exception as e:
            print("⚠ debug.py not loaded:", e)

        # 3分前通知ループ
        from commands.remind import start_loop
        await start_loop(self)

        await self.tree.sync()
        print("✅ setup_hook done")

intents = discord.Intents.default()
intents.message_content = True

bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("✅ on_ready:", bot.user)

if not TOKEN:
    raise RuntimeError("TOKEN が環境変数にありません（Renderの Environment Variables を確認）")

bot.run(TOKEN)
