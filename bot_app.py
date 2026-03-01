# bot_app.py（on_interaction部分だけでもOK。丸ごと差し替えでもOK）
import os
import asyncio
import traceback

import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager

from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.notify_panel import register as register_notify_panel   # 使ってるなら
from commands.set_manager_role import register as register_manager_role

from bot_interact import handle_interaction

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.guilds = True


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
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
        try:
            # ✅ component(ボタン/セレクト)だけ自前処理
            if interaction.type == discord.InteractionType.component:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()  # componentはephemeralじゃなくてOK
                except Exception:
                    pass

                try:
                    await handle_interaction(self, interaction)
                except Exception:
                    print("on_interaction(component) error")
                    print(traceback.format_exc())
                return

            # ✅ それ以外（スラッシュ等）は tree に渡す（バージョン差で落ちない）
            try:
                fn = getattr(self.tree, "_from_interaction", None)
                if fn is None:
                    return

                ret = fn(interaction)  # coroutine の場合もある / Noneの場合もある
                if asyncio.iscoroutine(ret):
                    await ret
                # ret が None でもOK（awaitしない）
            except Exception:
                print("on_interaction(app_commands) error")
                print(traceback.format_exc())

        except Exception:
            print("on_interaction fatal")
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
    backoff = 5
    while True:
        client = MyClient()
        try:
            await client.start(token)
            return
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                print(f"⚠️ 429 Too Many Requests. sleep {backoff}s then retry...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            raise
        except Exception:
            print("❌ fatal error (run_bot)")
            print(traceback.format_exc())
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)


def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")
    asyncio.run(run_bot_with_backoff(TOKEN))


if __name__ == "__main__":
    main()