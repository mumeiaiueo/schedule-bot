# bot_app.py
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

from bot_interact import handle_interaction

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()


async def _safe_defer(interaction: discord.Interaction):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

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
        try:
            if interaction.type == discord.InteractionType.component:
                await _safe_defer(interaction)
                await handle_interaction(self, interaction)
        except Exception:
            print("on_interaction error")
            print(traceback.format_exc())


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception:
        print("reminder_loop error")
        print(traceback.format_exc())


async def run_bot(token: str):
    backoff = 10
    while True:
        client = MyClient()
        try:
            await client.start(token)
            return
        except discord.errors.HTTPException as e:
            if getattr(e, "status", None) == 429:
                print(f"⚠️ 429 Too Many Requests. sleep {backoff}s")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            print("HTTPException:", repr(e))
        except Exception as e:
            print("start failed:", repr(e))

        print(f"retry after {backoff}s")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 300)


def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")
    asyncio.run(run_bot(TOKEN))


if __name__ == "__main__":
    main()