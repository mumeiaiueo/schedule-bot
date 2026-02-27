# bot_app.py
print("🔥 BOOT bot_app.py v2026-02-28 STABLE 🔥")

import traceback
import discord
from discord.ext import tasks

from utils.data_manager import DataManager

from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify
from commands.notify_panel import register as register_notify_panel
from commands.set_manager_role import register as register_manager_role

from bot_interact import handle_interaction


intents = discord.Intents.default()


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # setup wizard state
        self.setup_state: dict[int, dict] = {}

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception:
                print("⚠️ sync error")
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user}")

        if not reminder_loop.is_running():
            reminder_loop.start(self)

    async def on_interaction(self, interaction: discord.Interaction):
        # ここで全部さばく（version差分に強い）
        await handle_interaction(self, interaction)


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception as e:
        print("reminder_loop error:", repr(e))
        print(traceback.format_exc())


async def run_bot_once(token: str):
    """
    1回起動して、落ちたら例外を投げる（再起動は main.py がやる）
    """
    client = MyClient()
    try:
        await client.start(token)
    finally:
        try:
            if reminder_loop.is_running():
                reminder_loop.stop()
        except Exception:
            pass
        try:
            await client.close()
        except Exception:
            pass