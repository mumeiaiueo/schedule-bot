print("🔥 BOOT MARKER v2026-02-23-0835 🔥")
import asyncio
import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager
from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False  # ★再接続のたびにsync連打しない

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)

    async def on_ready(self):
        # ★syncは最初の1回だけ（429対策）
        if not self._synced:
            await self.tree.sync()
            self._synced = True

        print(f"✅ Logged in as {self.user}")

        if not reminder_loop.is_running():
            reminder_loop.start(self)

client = MyClient()

@tasks.loop(seconds=60)
async def reminder_loop(bot: MyClient):
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception as e:
        print("reminder_loop error:", repr(e))

async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN が未設定です")

    # 429対策：失敗しても落ちずに待って再試行
    while True:
        try:
            async with client:
                await client.start(TOKEN)
        except discord.HTTPException as e:
            print("discord HTTPException:", repr(e))
            await asyncio.sleep(90)
        except Exception as e:
            print("fatal error:", repr(e))
            await asyncio.sleep(90)

asyncio.run(main())