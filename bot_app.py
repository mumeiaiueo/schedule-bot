# bot_app.py（完全コピペ版：モーダル対応・40060/既ACK事故を減らす）
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

        self._synced = False

    async def setup_hook(self):
        # register commands
        register_setup_channel(self.tree, self.dm)
        register_reset_channel(self.tree, self.dm)
        register_set_manager_role(self.tree, self.dm)

        # ✅ sync は起動直後に1回だけ
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception:
                print("⚠️ sync error")
                print(traceback.format_exc())

        # ✅ 3分前通知ループ開始（重複起動防止）
        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (id={self.user.id})")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ ここがポイント：
        - component(ボタン/セレクト) をここで先に defer しない
          → deferすると「モーダルを開けない」「既ACK(40060)」の原因になる
        - ACK/返信は bot_interact 側で custom_id を見て適切に行う
        """
        try:
            if interaction.type in (
                discord.InteractionType.component,
                discord.InteractionType.modal_submit,
            ):
                await handle_interaction(self, interaction)
                return

            # スラッシュコマンドは通常処理へ
            if interaction.type == discord.InteractionType.application_command:
                # discord.pyの内部処理に任せる（安定）
                await super().on_interaction(interaction)
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