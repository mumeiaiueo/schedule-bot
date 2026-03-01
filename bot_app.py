# bot_app.py
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_interaction

# commands
from commands.setup_channel import register as register_setup_channel
from commands.reset_channel import register as register_reset_channel
from commands.set_manager_role import register as register_set_manager_role


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()

        # setup wizard state: {user_id: dict}
        self.setup_state = {}

    async def setup_hook(self):
        # register commands
        register_setup_channel(self.tree, self.dm)
        register_reset_channel(self.tree, self.dm)
        register_set_manager_role(self.tree, self.dm)

        await self.tree.sync()
        self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 40060防止の安定処理
        - component / modal はここでACKして bot_interact に流す
        - slash command は tree に渡す
        """
        try:
            # ボタン・セレクト
            if interaction.type == discord.InteractionType.component:
                try:
                    if not interaction.response.is_done():
                        # updateではなくdeferでOK（followup/ephemeralを使うため）
                        await interaction.response.defer()
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # モーダル送信（タイトル入力）
            if interaction.type == discord.InteractionType.modal_submit:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # スラッシュコマンド
            if interaction.type == discord.InteractionType.application_command:
                await self.tree._call(interaction)
                return

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())

    # ✅ 3分前通知ループ
    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            await self.dm.send_3min_reminders(self)
        except Exception:
            print("❌ reminder loop error")
            print(traceback.format_exc())


bot = BotApp()