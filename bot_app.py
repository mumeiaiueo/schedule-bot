# bot_app.py（完全コピペ版）
import os
import asyncio
import traceback

import discord
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv

from utils.data_manager import DataManager
from bot_interact import handle_interaction

# ✅ コマンド登録（あなたのプロジェクトにある想定）
from commands.setup_channel import register as register_setup_channel
from commands.reset_channel import register as register_reset_channel
from commands.set_manager_role import register as register_manager_role
# もし使ってるなら ↓ も追加してOK（無いならコメントのまま）
# from commands.notify_panel import register as register_notify_panel


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.guilds = True  # app_commandsに必要
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

    async def setup_hook(self):
        # ✅ コマンド登録
        register_setup_channel(self.tree, self.dm)
        register_reset_channel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)
        # register_notify_panel(self.tree, self.dm)  # 使うなら有効化

    async def on_ready(self):
        # ✅ syncは起動時1回だけ
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception:
                print("⚠️ sync error")
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user}")

        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    # ✅ Interaction 安定処理（componentだけ自前、slashは標準へ）
    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # ボタン・セレクト（component）
            if interaction.type == discord.InteractionType.component:
                # 3秒以内ACK（Unknown interaction対策）
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
                except Exception:
                    pass

                try:
                    await handle_interaction(self, interaction)
                except Exception:
                    print("❌ handle_interaction error")
                    print(traceback.format_exc())
                return

            # スラッシュコマンド等（application_command）は標準処理へ
            await super().on_interaction(interaction)

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())

    # ✅ 3分前通知ループ（30秒おき）
    @tasks.loop(seconds=30, reconnect=True)
    async def reminder_loop(self):
        try:
            if self.is_closed() or not self.is_ready():
                return
            await self.dm.send_3min_reminders(self)
        except Exception:
            print("❌ reminder loop error")
            print(traceback.format_exc())


async def run_bot_with_backoff():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")

    backoff = 5
    while True:
        bot = BotApp()
        try:
            await bot.start(TOKEN)
            return
        except discord.HTTPException as e:
            # 429 対策
            if getattr(e, "status", None) == 429:
                print(f"⚠️ 429 Too Many Requests. sleep {backoff}s then retry...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)  # 最大5分
                continue
            raise
        except Exception:
            print("❌ fatal error (run_bot)")
            print(traceback.format_exc())
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


def main():
    asyncio.run(run_bot_with_backoff())


if __name__ == "__main__":
    main()