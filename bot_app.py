# bot_app.py
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_component_or_modal

# commands（今のファイル名に合わせる）
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
        """
        重要:
        - /setup などのスラッシュは **ここで defer しない**
        - ボタン/セレクト/モーダルだけ defer して handler に渡す
        """
        try:
            if interaction.type == discord.InteractionType.component:
                # ボタン/セレクト
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
                except Exception:
                    pass
                await handle_component_or_modal(self, interaction)
                return

            if interaction.type == discord.InteractionType.modal_submit:
                # モーダル送信
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass
                await handle_component_or_modal(self, interaction)
                return

            # スラッシュコマンドは tree に任せる
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