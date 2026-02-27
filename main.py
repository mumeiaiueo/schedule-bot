# main.py  （B方式：custom_id を main.py で処理）
print("🔥 BOOT MARKER v2026-02-27 B-mode stable FINAL FIX 🔥")

import asyncio
import os
import socket
import traceback
from urllib.parse import urlparse

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


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    """3秒制限回避。既に応答済みなら何もしない。"""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    """二重返信でも落ちない送信。"""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


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

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 安定版:
        - component(ボタン/セレクト) はここで処理
        - application_command(スラッシュ) は process_interaction に渡す（公式）
        """
        try:
            # -------------------------
            # 1) スラッシュコマンド等は tree に渡す（公式）
            # -------------------------
            if interaction.type == discord.InteractionType.application_command:
                try:
                    result = self.tree._from_interaction(interaction)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass
                return
                    
            # -------------------------
            # 2) component（ボタン/セレクト）
            # -------------------------
            if interaction.type != discord.InteractionType.component:
                return

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            if not custom_id or not isinstance(custom_id, str):
                return

            print("[COMPONENT]", custom_id)

            await safe_defer(interaction, ephemeral=True)

            # panel:slot:<panel_id>:<slot_id>
            if custom_id.startswith("panel:slot:"):
                parts = custom_id.split(":")
                if len(parts) != 4:
                    await safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                slot_id = int(parts[3])

                ok, msg = await self.dm.toggle_reserve(
                    slot_id=slot_id,
                    user_id=str(interaction.user.id),
                    user_name=getattr(interaction.user, "display_name", str(interaction.user)),
                )

                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg, ephemeral=True)
                return

            # panel:breaktoggle:<panel_id>
            if custom_id.startswith("panel:breaktoggle:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                view = await self.dm.build_break_select_view(panel_id)

                # defer 済みなので followup で view 付き送信
                try:
                    await interaction.followup.send(
                        "⌚️ 休憩にする/解除する時間を選んでね👇",
                        view=view,
                        ephemeral=True,
                    )
                except Exception:
                    await safe_send(interaction, "❌ 表示に失敗しました（もう一度押して）", ephemeral=True)
                return

            # panel:breakselect:<panel_id>
            if custom_id.startswith("panel:breakselect:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await safe_send(interaction, "❌ セレクト形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                values = data.get("values") or []
                if not values:
                    await safe_send(interaction, "❌ 選択値が取得できませんでした", ephemeral=True)
                    return

                slot_id = int(values[0])

                ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg, ephemeral=True)
                return

            # 想定外 custom_id
            await safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)


client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready():
        return
    if bot.is_closed():
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
        if "Session is closed" in msg:
            backoff = max(backoff, 120)
        if "Name or service not known" in msg or "Temporary failure in name resolution" in msg:
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

    try:
        await client.start(TOKEN)
    finally:
        try:
            if reminder_loop.is_running():
                reminder_loop.stop()
        except Exception:
            pass

        try:
            await client.close()
        except Exception:
            pass


asyncio.run(main())