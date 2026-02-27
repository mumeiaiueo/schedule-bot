# bot_app.py
import asyncio
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

from bot_interact import handle_component_interaction


intents = discord.Intents.default()


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

    async def setup_hook(self):
        # slash commands 登録
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
        # コマンド同期（最初の1回だけ）
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
        """
        ここが最重要。
        - /コマンド(application_command, autocomplete) は tree に渡す
        - ボタン/セレクト(component) だけ自前処理
        """
        try:
            if interaction.type in (
                discord.InteractionType.application_command,
                discord.InteractionType.autocomplete,
            ):
                res = self.tree._from_interaction(interaction)
                if asyncio.iscoroutine(res):
                    await res
                return

            if interaction.type == discord.InteractionType.component:
                await handle_component_interaction(self, interaction)
                return

            # それ以外は無視（必要なら追加）
        except Exception:
            print("on_interaction error:")
            print(traceback.format_exc())
            # ここで落とさない（落ちると再起動ループ→429になりやすい）


# ------------------------------
# reminder loop
# ------------------------------
@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception:
        print("reminder_loop error:")
        print(traceback.format_exc())


async def run_bot_once(token: str):
    client = MyClient()
    await client.start(token)


async def run_bot_forever(token: str):
    """
    落ちても即ループしない（429/Cloudflare回避のためバックオフ）
    """
    backoff = 5
    while True:
        try:
            await run_bot_once(token)
        except Exception:
            print("❌ bot crashed:")
            print(traceback.format_exc())
            print(f"⏸ retry after {backoff}s")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)  # 最大5分
        else:
            backoff = 5