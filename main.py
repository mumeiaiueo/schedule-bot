print("🔥 STABLE FINAL CORE BUILD 🔥")

import os
import asyncio
import traceback

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager

from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify
from commands.notify_panel import register as register_notify_panel
from commands.set_manager_role import register as register_manager_role

load_dotenv()

TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()

intents = discord.Intents.default()


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self.synced = False

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
        if not self.synced:
            try:
                await self.tree.sync()
                print("✅ commands synced")
                self.synced = True
            except Exception:
                print("❌ sync error")
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user} (guilds={len(self.guilds)})")

        if not reminder_loop.is_running():
            reminder_loop.start()

client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop():
    try:
        if not client.is_ready() or client.is_closed():
            return
        await client.dm.send_3min_reminders(client)
    except Exception:
        print("⚠️ reminder loop error")
        print(traceback.format_exc())


@reminder_loop.before_loop
async def before_loop():
    await client.wait_until_ready()
    await asyncio.sleep(5)


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")

    await client.start(TOKEN)


asyncio.run(main())