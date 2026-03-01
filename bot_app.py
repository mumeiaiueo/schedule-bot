import os
import traceback
import discord
from discord.ext import tasks

from utils.data_manager import DataManager
from bot_interact import handle_interaction

class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self.setup_state = {}

    async def setup_hook(self):
        # コマンド登録
        @self.tree.command(name="setup", description="募集パネル作成")
        async def setup_cmd(interaction: discord.Interaction):
            from views.setup_wizard import build_setup_embed, build_setup_view
            embed = build_setup_embed({"step":1,"day":"today"})
            view = build_setup_view({"step":1,"day":"today"})
            await interaction.response.send_message(embed=embed, view=view)

        @self.tree.command(name="reset", description="今日/明日の募集削除")
        async def reset_cmd(interaction: discord.Interaction):
            await interaction.response.send_message("削除は次で実装", ephemeral=True)

        @self.tree.command(name="manager_role", description="管理ロール設定")
        async def manager_cmd(interaction: discord.Interaction, role: discord.Role=None):
            await interaction.response.send_message("管理ロールは次で実装", ephemeral=True)

        if os.getenv("SYNC_COMMANDS","0") == "1":
            await self.tree.sync()
            print("✅ synced")

        self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            if interaction.type in (
                discord.InteractionType.component,
                discord.InteractionType.modal_submit,
            ):
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await handle_interaction(self, interaction)
            else:
                await self.tree.process_interaction(interaction)
        except Exception:
            print(traceback.format_exc())

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            await self.dm.send_3min_reminders(self)
        except:
            pass


async def run_bot(token: str):
    bot = BotApp()
    await bot.start(token)