# bot_app.py（on_interactionを安全に）
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_component_or_modal

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

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

        await self.tree.sync()
        self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # ✅ ボタン/セレクト
            if interaction.type == discord.InteractionType.component:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await handle_component_or_modal(self, interaction)
                return

            # ✅ モーダル
            if interaction.type == discord.InteractionType.modal_submit:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await handle_component_or_modal(self, interaction)
                return

            # ✅ スラッシュコマンドは「discord.py本体」に任せる（これが重要）
            await super().on_interaction(interaction)

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