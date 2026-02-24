print("🔥 BOOT MARKER v2026-02-24-stable-reminder FULL 🔥")

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
        custom_id 方式のボタン/セレクトを最優先で処理する。
        """
        try:
            # component（ボタン/セレクト）以外は通常処理へ
            if interaction.type != discord.InteractionType.component:
                return await super().on_interaction(interaction)

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            if not custom_id or not isinstance(custom_id, str):
                return await super().on_interaction(interaction)

            # 3秒制限回避：まずdefer（すでに応答済みなら無視）
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)
            except Exception:
                pass

            # ========== panel:slot:<panel_id>:<slot_id> ==========
            if custom_id.startswith("panel:slot:"):
                parts = custom_id.split(":")
                if len(parts) != 4:
                    await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                slot_id = int(parts[3])

                # デバッグログ（押せてるか確認用）
                print(f"[CLICK] guild={interaction.guild_id} ch={interaction.channel_id} panel={panel_id} slot={slot_id} user={interaction.user.id}")

                # DataManagerが2引数版/3引数版どっちでも動くようにする
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

            # ========== panel:breaktoggle:<panel_id> ==========
            if custom_id.startswith("panel:breaktoggle:"):
                if not is_admin(interaction):
                    await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                print(f"[BREAKTOGGLE] panel={panel_id} by={interaction.user.id}")

                # DataManagerに休憩機能が無い場合も落とさない
                if not hasattr(self.dm, "build_break_select_view"):
                    await interaction.followup.send("⚠️ 休憩機能が未実装です（DataManagerに追加が必要）", ephemeral=True)
                    return

                view = await self.dm.build_break_select_view(panel_id)
                await interaction.followup.send("休憩にする/解除する時間を選んでね👇", view=view, ephemeral=True)
                return

            # ========== panel:breakselect:<panel_id> ==========
            if custom_id.startswith("panel:breakselect:"):
                if not is_admin(interaction):
                    await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await interaction.followup.send("❌ セレクト形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                values = data.get("values") or []
                if not values:
                    await interaction.followup.send("❌ 選択値が取得できませんでした", ephemeral=True)
                    return

                slot_id = int(values[0])
                print(f"[BREAKSELECT] panel={panel_id} slot={slot_id} by={interaction.user.id}")

                if not hasattr(self.dm, "toggle_break_slot"):
                    await interaction.followup.send("⚠️ 休憩機能が未実装です（DataManagerに追加が必要）", ephemeral=True)
                    return

                ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
                await self.dm.render_panel(self, panel_id)
                await interaction.followup.send(msg, ephemeral=True)
                return

            # それ以外は通常処理へ
            return await super().on_interaction(interaction)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            try:
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