print("🔥 BOOT MARKER v2026-02-24-stable-reminder FULL v2 🔥")

import asyncio
import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv

import socket
import traceback
from urllib.parse import urlparse

from utils.data_manager import DataManager
from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify
from commands.notify_panel import register as register_notify_panel
from commands.set_manager_role import register as register_manager_role

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")

intents = discord.Intents.default()


def supabase_host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except Exception:
        return None


def is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # reminder のバックオフ制御
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0  # loop.time()

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)


    async def on_ready(self):
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception as e:
                print("⚠️ tree.sync failed:", repr(e))
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user}")

        if not reminder_loop.is_running():
            reminder_loop.start(self)


        """
        - component(ボタン/セレクト)は custom_id を自前処理
        - それ以外(スラッシュコマンド等)は tree に処理させる
        """
        try:
            # =========================
            # 1) ボタン/セレクト処理
            # =========================
            if interaction.type == discord.InteractionType.component:
                data = interaction.data or {}
                custom_id = data.get("custom_id")
                if not custom_id or not isinstance(custom_id, str):
                    return  # 何もしない

                # 3秒制限回避：先にdefer
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass

                # panel:slot:<panel_id>:<slot_id>
                if custom_id.startswith("panel:slot:"):
                    parts = custom_id.split(":")
                    if len(parts) != 4:
                        await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                        return

                    panel_id = int(parts[2])
                    slot_id = int(parts[3])

                    print(f"[CLICK] guild={interaction.guild_id} ch={interaction.channel_id} panel={panel_id} slot={slot_id} user={interaction.user.id}")

                    # toggle_reserve が 2引数/3引数どっちでも動くようにする
                    try:
                        ok, msg = await self.dm.toggle_reserve(
                            slot_id,
                            str(interaction.user.id),
                            interaction.user.display_name,
                        )
                    except TypeError:
                        ok, msg = await self.dm.toggle_reserve(
                            slot_id,
                            str(interaction.user.id),
                        )

                    await self.dm.render_panel(self, panel_id)
                    await interaction.followup.send(msg, ephemeral=True)
                    return

                # panel:breaktoggle:<panel_id>
                if custom_id.startswith("panel:breaktoggle:"):
                    if not is_admin(interaction):
                        await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                        return
                    await interaction.followup.send("⚠️ 休憩機能はまだ未対応です（必要なら実装します）", ephemeral=True)
                    return

                # panel:breakselect:<panel_id>
                if custom_id.startswith("panel:breakselect:"):
                    if not is_admin(interaction):
                        await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                        return
                    await interaction.followup.send("⚠️ 休憩機能はまだ未対応です（必要なら実装します）", ephemeral=True)
                    return

                # custom_id が想定外なら何もしない
                return

            # =========================
            # 2) スラッシュコマンド等
            # =========================
            await self.tree.process_interaction(interaction)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await interaction.followup.send(f"❌ エラー: {repr(e)}", ephemeral=True)
            except Exception:
                pass


client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready():
        return

    loop = asyncio.get_running_loop()

    if bot._reminder_pause_until and loop.time() < bot._reminder_pause_until:
        return

    try:
        await bot.dm.send_3min_reminders(bot)

        bot._reminder_fail_count = 0
        bot._reminder_pause_until = 0.0

    except Exception as e:
        bot._reminder_fail_count += 1

        print("reminder_loop error:", repr(e))
        print(traceback.format_exc())

        backoff = min(600, 60 * (2 ** (bot._reminder_fail_count - 1)))

        msg = repr(e)
        if "Name or service not known" in msg or "ConnectError" in msg or "Temporary failure in name resolution" in msg:
            backoff = max(backoff, 120)

        bot._reminder_pause_until = loop.time() + backoff
        print(f"⏸ reminder paused for {backoff}s (fail_count={bot._reminder_fail_count})")


@reminder_loop.before_loop
async def before_reminder_loop():
    await client.wait_until_ready()
    await asyncio.sleep(10)

    host = supabase_host_from_url(SUPABASE_URL)
    if not host:
        print("⚠️ SUPABASE_URL is missing or invalid. DNS check skipped.")
        return

    try:
        ip = socket.gethostbyname(host)
        print(f"✅ DNS check OK: {host} -> {ip}")
    except Exception as e:
        print("⚠️ DNS check failed:", repr(e))


async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN が未設定です")

    while True:
        try:
            async with client:
                await client.start(TOKEN)

        except discord.HTTPException as e:
            print("discord HTTPException:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(90)

        except Exception as e:
            print("fatal error:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(90)


asyncio.run(main())