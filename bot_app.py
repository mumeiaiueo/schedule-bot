# bot_app.py
import traceback
import asyncio

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
        # ✅ register commands
        register_setup_channel(self.tree, self.dm)
        register_reset_channel(self.tree, self.dm)
        register_set_manager_role(self.tree, self.dm)

        # ✅ sync once on boot
        await self.tree.sync()

        # ✅ start reminder loop
        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user} (guilds={len(self.guilds)})")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 40060防止の安定処理
        - component / modal はここで defer → bot_interact に流す
        - slash は CommandTree に渡す（※ super().on_interaction は呼ばない）
        """
        try:
            # ボタン・セレクト
            if interaction.type == discord.InteractionType.component:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()  # followup/ephemeralを使う想定
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # モーダル送信（タイトル入力など）
            if interaction.type == discord.InteractionType.modal_submit:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass

                await handle_interaction(self, interaction)
                return

            # スラッシュコマンド（アプリコマンド）
            if interaction.type == discord.InteractionType.application_command:
                # discord.py のバージョン差で super().on_interaction は無いので使わない
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
    """
    ✅ main.py から呼ばれる唯一の起動口
    - 429(Cloudflare/Too Many Requests) が来たら落とさず待って再試行
    """
    bot = BotApp()

    backoff = 15  # 秒（429時に増やす）
    while True:
        try:
            async with bot:
                await bot.start(token, reconnect=True)
            # 正常終了したらループを抜ける
            return

        except discord.HTTPException as e:
            # 429 / Cloudflare系のブロックは「落とすと再起動→連打→悪化」なので待つ
            if getattr(e, "status", None) == 429:
                print("⚠️ Discord login rate-limited (429). Backing off...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 600)  # 最大10分
                continue

            print("❌ discord.HTTPException")
            print(repr(e))
            await asyncio.sleep(10)
            continue

        except Exception:
            print("❌ run_bot fatal error")
            print(traceback.format_exc())
            await asyncio.sleep(10)
            continue