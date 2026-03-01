# bot_app.py
import os
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
        - slash command は CommandTree に処理させる
        """
        try:
            # -------------------------
            # ① ボタン・セレクト（component）
            # -------------------------
            if interaction.type == discord.InteractionType.component:
                # 先にACK（これをやらないと3秒で40060になりやすい）
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # -------------------------
            # ② モーダル送信（modal_submit）
            # -------------------------
            if interaction.type == discord.InteractionType.modal_submit:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # -------------------------
            # ③ スラッシュコマンド（application_command）
            # -------------------------
            if interaction.type == discord.InteractionType.application_command:
                # discord.py 2.x の推奨ルート：Client.process_application_commands を使う
                # （無い環境もあるので安全に分岐）
                try:
                    proc = getattr(self, "process_application_commands", None)
                    if proc:
                        await proc(interaction)
                        return
                except Exception:
                    # 落ちたら tree の internal にフォールバック
                    pass

                # フォールバック（環境差でprocess_application_commandsが無い場合用）
                try:
                    call = getattr(self.tree, "_call", None)
                    if call:
                        await call(interaction)
                        return
                except Exception:
                    pass

                # 最終：何もしない（ここで例外出すより安全）
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


def _get_token() -> str:
    # Renderでよくある命名揺れを全部拾う
    tok = (
        os.getenv("DISCORD_TOKEN")
        or os.getenv("TOKEN")
        or os.getenv("BOT_TOKEN")
    )
    if not tok or not str(tok).strip():
        raise RuntimeError("❌ DISCORD_TOKEN（または TOKEN / BOT_TOKEN）が未設定です。RenderのEnvironmentを確認してください。")
    return str(tok).strip()


bot = BotApp()

if __name__ == "__main__":
    TOKEN = _get_token()
    bot.run(TOKEN)