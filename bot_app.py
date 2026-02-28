# bot_app.py
import os
import asyncio
import traceback

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager

from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify
from commands.notify_panel import register as register_notify_panel
from commands.set_manager_role import register as register_manager_role

from bot_interact import handle_interaction

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
# 必須：app_commands は guilds intent が必要
intents.guilds = True


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

    async def setup_hook(self):
        # コマンド登録
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
        # sync は起動直後に1回だけ
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception:
                print("⚠️ sync error")
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user}")

        if not reminder_loop.is_running():
            reminder_loop.start(self)

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ ここが重要：
        - component(ボタン/セレクト)だけ自前処理（3秒以内に defer でACK）
        - それ以外は CommandTree に渡す（super() は呼ばない）
        """
        try:
            if interaction.type == discord.InteractionType.component:
                # 3秒以内ACK（Unknown interaction 10062対策）
                try:
                    if not interaction.response.is_done():
                        # ※ここは ephemeral=False 推奨（元メッセージ編集することが多いので）
                        await interaction.response.defer()
                except Exception:
                    pass

                try:
                    await handle_interaction(self, interaction)
                except Exception:
                    print("on_interaction(component) error")
                    print(traceback.format_exc())
                return

            # ✅ スラッシュコマンド等 → CommandTree に任せる
            # （あなたの環境では process_interaction は無い。_from_interaction が正解）
            await self.tree._from_interaction(interaction)

        except Exception:
            print("on_interaction error")
            print(traceback.format_exc())


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception:
        print("reminder_loop error")
        print(traceback.format_exc())


async def run_bot_with_backoff(token: str):
    """
    ✅ 429 が出ても即死しない（待って再試行）
    Render の再起動連打 → 429 の悪循環を止める
    """
    backoff = 5
    while True:
        client = MyClient()
        try:
            await client.start(token)
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
            # 連続クラッシュでログイン連打しないよう待つ
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")
    asyncio.run(run_bot_with_backoff(TOKEN))


if __name__ == "__main__":
    main()