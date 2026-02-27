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

from bot_interact import handle_interaction

intents = discord.Intents.default()


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # ✅ setupウィザード状態（ユーザーごと）
        self.setup_state: dict[int, dict] = {}

        # ✅ reminder の暴走対策（落ちにくく）
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0  # loop.time()

    def get_setup_state(self, user_id: int) -> dict:
        st = self.setup_state.get(user_id)
        if st is None:
            st = {
                "day": None,               # "today" | "tomorrow"
                "start_hour": None,
                "start_min": None,
                "end_hour": None,
                "end_min": None,
                "interval": None,          # 20/25/30
                "notify_channel_id": None, # 必須
                "everyone": False,         # 任意
                "title": None,             # 任意
            }
            self.setup_state[user_id] = st
        return st

    def clear_setup_state(self, user_id: int):
        self.setup_state.pop(user_id, None)

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

        # ✅ ready後に少し待ってから回す（Session is closed 系を減らす）
        if not reminder_loop.is_running():
            await asyncio.sleep(5)
            reminder_loop.start(self)

    async def on_interaction(self, interaction: discord.Interaction):
        await handle_interaction(self, interaction)


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return

    loop = asyncio.get_running_loop()
    if bot._reminder_pause_until and loop.time() < bot._reminder_pause_until:
        return

    try:
        await bot.dm.send_3min_reminders(bot)
        bot._reminder_fail_count = 0
        bot._reminder_pause_until = 0.0
    except Exception as e:
        bot._reminder_fail_count += 1
        print("reminder_loop error:", repr(e))
        print(traceback.format_exc())

        # 失敗時はバックオフ
        backoff = min(600, 60 * (2 ** (bot._reminder_fail_count - 1)))
        msg = repr(e)
        if "Session is closed" in msg:
            backoff = max(backoff, 120)
        bot._reminder_pause_until = loop.time() + backoff
        print(f"⏸ reminder paused for {backoff}s (fail_count={bot._reminder_fail_count})")


async def run_bot(token: str):
    client = MyClient()
    await client.start(token)