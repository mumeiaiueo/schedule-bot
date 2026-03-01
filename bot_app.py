import os
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_interaction

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

        # setup wizard state: {user_id: dict}
        self.setup_state = {}

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

        # ✅ 429対策：必要な時だけ同期
        if os.getenv("SYNC_COMMANDS", "0") == "1":
            await self.tree.sync()
            print("✅ commands synced (SYNC_COMMANDS=1)")
        else:
            print("ℹ️ skip tree.sync (set SYNC_COMMANDS=1 to sync)")

        self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (id={self.user.id})")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 安定処理
        - component/modal はここで defer して bot_interact に渡す
        - slash は tree.process_interaction に渡す
        """
        try:
            if interaction.type in (
                discord.InteractionType.component,
                discord.InteractionType.modal_submit,
            ):
                try:
                    if not interaction.response.is_done():
                        # component は通常 defer()、modal は ephemeral defer()
                        if interaction.type == discord.InteractionType.modal_submit:
                            await interaction.response.defer(ephemeral=True)
                        else:
                            await interaction.response.defer()
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # slash command 等
            await self.tree.process_interaction(interaction)

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


async def run_bot(token: str):
    bot = BotApp()
    await bot.start(token)