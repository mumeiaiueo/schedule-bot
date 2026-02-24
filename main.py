print("🔥 BOOT MARKER v2026-02-24-stable-reminder 🔥")

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

    async def on_ready(self):
        # sync は起動後1回だけ（429対策）
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

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ボタン/セレクトをここで処理して「インタラクションに失敗しました」を防ぐ版
        """
        try:
            # component以外は通常処理へ（スラッシュコマンド等）
            if interaction.type != discord.InteractionType.component:
                return await super().on_interaction(interaction)

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            if not custom_id or not isinstance(custom_id, str):
                return await super().on_interaction(interaction)

            # ---- ここから custom_id を自前処理 ----

            # panel:slot:<panel_id>:<slot_id>
            if custom_id.startswith("panel:slot:"):
                # 3秒制限回避：先にdefer（返信枠確保）
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)

                parts = custom_id.split(":")
                if len(parts) != 4:
                    await safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                slot_id = int(parts[3])

                # DataManager(あなたの版)は toggle_reserve(slot_id, user_id)
                ok, msg = await self.dm.toggle_reserve(slot_id, str(interaction.user.id))

                # パネル再描画
                await self.dm.render_panel(self, panel_id)

                await safe_send(interaction, msg, ephemeral=True)
                return

            # 休憩ボタン/セレクトが残っている場合：落とさないための保険
            if custom_id.startswith("panel:breaktoggle:") or custom_id.startswith("panel:breakselect:"):
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
                await safe_send(
                    interaction,
                    "⚠️ この版は休憩機能が未実装です（休憩ボタンを消すか、休憩機能を追加する必要があります）",
                    ephemeral=True
                )
                return

            # それ以外は通常処理へ
            return await super().on_interaction(interaction)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception:
                pass
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)


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