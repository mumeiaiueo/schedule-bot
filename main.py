import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

class Bot(commands.Bot):
    async def setup_hook(self):
        # コマンド登録
        from commands.create import setup as create_setup
        from commands.settings import setup as settings_setup  # notifysetがここなら
        from commands.debug import setup as debug_setup

        create_setup(self)
        settings_setup(self)
        debug_setup(self)

        # リマインドループ開始
        from commands.remind import start_loop
        await start_loop(self)

        await self.tree.sync()

intents = discord.Intents.default()
intents.message_content = True

bot = Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("起動完了:", bot.user)

bot.run(TOKEN)
