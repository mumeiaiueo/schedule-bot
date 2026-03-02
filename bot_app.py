# bot_app.py
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_component  # ← ここ重要（あなたの関数名に合わせる）

# commands
from commands.setup import register as register_setup
from commands.reset import register as register_reset
from commands.manager_role import register as register_manager_role


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()

        # ✅ ウィザード状態を持つ
        self.wizard_state = {}

    async def setup_hook(self):
        register_setup(self.tree, self.dm, self.wizard_state)
        register_reset(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

        await self.tree.sync()
        self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ ここでは defer しない（40060防止）
        ボタン/セレクト/モーダルは bot_interact 側で処理
        """
        try:
            if interaction.type in (
                discord.InteractionType.component,
                discord.InteractionType.modal_submit,
            ):
                await handle_component(self, interaction)
                return

            if interaction.type == discord.InteractionType.application_command:
                await self.tree._call(interaction)
                return

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            await self.dm.send_3min_reminders(self)
        except Exception:
            print("❌ reminder loop error")
            print(traceback.format_exc())


async def run_bot(token: str):
    bot = BotApp()
    await bot.start(token)