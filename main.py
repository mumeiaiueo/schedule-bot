# main.py
print("🔥 BOOT MARKER v2026-02-27 B-mode stable FINAL COMPLETE v3 (restart-safe) 🔥")

import asyncio
import os
import socket
import traceback
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone

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
from views.setup_wizard import build_setup_embed, build_setup_view

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")

intents = discord.Intents.default()
JST = timezone(timedelta(hours=9))


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


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


# ✅ tasks.loop はグローバルでOK（bot を引数でもらう）
@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot):
    if not bot.is_ready() or bot.is_closed():
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
        bot._reminder_pause_until = loop.time() + backoff
        print(f"⏸ reminder paused for {backoff}s (fail_count={bot._reminder_fail_count})")


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # setup wizard state（ユーザーごと）
        self.setup_state: dict[int, dict] = {}

        # reminder backoff
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0

        # DNS check 1回だけ
        self._dns_checked = False

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)
        register_notify_panel(self.tree, self.dm)
        register_manager_role(self.tree, self.dm)

    async def on_ready(self):
        # DNS check（ログ用・落とさない）
        if (not self._dns_checked) and SUPABASE_URL:
            self._dns_checked = True
            host = supabase_host_from_url(SUPABASE_URL)
            if host:
                try:
                    ip = socket.gethostbyname(host)
                    print(f"✅ DNS check OK: {host} -> {ip}")
                except Exception as e:
                    print("⚠️ DNS check failed:", repr(e))

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

    # -------------------------
    # setup wizard helpers
    # -------------------------
    def _get_setup_state(self, user_id: int) -> dict:
        st = self.setup_state.get(user_id)
        if st is None:
            st = {
                "day": None,
                "start_h": None, "start_m": None,
                "end_h": None, "end_m": None,
                "interval": None,
                "notify_channel_id": None,
                "everyone": False,
                "title": None,
            }
            self.setup_state[user_id] = st
        return st

    async def _edit_setup_ephemeral(self, interaction: discord.Interaction):
        st = self._get_setup_state(interaction.user.id)
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        try:
            await interaction.edit_original_response(embed=embed, view=view)
        except Exception:
            pass

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # slash系は tree に任せる
            if interaction.type in (
                discord.InteractionType.application_command,
                discord.InteractionType.autocomplete,
                discord.InteractionType.modal_submit,
            ):
                try:
                    res = self.tree._from_interaction(interaction)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception:
                    pass
                return

            if interaction.type != discord.InteractionType.component:
                return

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            values = data.get("values") or []
            if not custom_id or not isinstance(custom_id, str):
                return

            # ACK（3秒回避）
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass

            # -----------------------------
            # panel buttons
            # -----------------------------
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
                await interaction.followup.send("⌚️ 休憩を選んでね👇", view=view, ephemeral=True)
                return

            if custom_id.startswith("panel:breakselect:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                    return
                parts = custom_id.split(":")
                if len(parts) != 3 or not values:
                    await safe_send(interaction, "❌ セレクトが不正です", ephemeral=True)
                    return
                panel_id = int(parts[2])
                slot_id = int(values[0])
                ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg, ephemeral=True)
                return

            # -----------------------------
            # setup wizard
            # -----------------------------
            if custom_id.startswith("setup:"):
                st = self._get_setup_state(interaction.user.id)

                if custom_id == "setup:day:today":
                    st["day"] = "today"
                elif custom_id == "setup:day:tomorrow":
                    st["day"] = "tomorrow"
                elif custom_id == "setup:start_h" and values:
                    st["start_h"] = values[0]
                elif custom_id == "setup:start_m" and values:
                    st["start_m"] = values[0]
                elif custom_id == "setup:end_h" and values:
                    st["end_h"] = values[0]
                elif custom_id == "setup:end_m" and values:
                    st["end_m"] = values[0]
                elif custom_id.startswith("setup:interval:"):
                    st["interval"] = int(custom_id.split(":")[-1])
                elif custom_id == "setup:notify_ch" and values:
                    st["notify_channel_id"] = str(values[0])
                elif custom_id == "setup:everyone:toggle":
                    st["everyone"] = not bool(st["everyone"])

                elif custom_id == "setup:cancel":
                    self.setup_state.pop(interaction.user.id, None)
                    try:
                        await interaction.edit_original_response(content="✅ キャンセルしました", embed=None, view=None)
                    except Exception:
                        pass
                    return

                elif custom_id == "setup:create":
                    missing = []
                    if not st.get("day"): missing.append("今日/明日")
                    if not (st.get("start_h") and st.get("start_m")): missing.append("開始")
                    if not (st.get("end_h") and st.get("end_m")): missing.append("終了")
                    if not st.get("interval"): missing.append("間隔")
                    if not st.get("notify_channel_id"): missing.append("通知チャンネル")

                    if missing:
                        await interaction.followup.send("❌ 未入力: " + " / ".join(missing), ephemeral=True)
                        await self._edit_setup_ephemeral(interaction)
                        return

                    today = datetime.now(JST).date()
                    day = today if st["day"] == "today" else today + timedelta(days=1)

                    sh, sm = int(st["start_h"]), int(st["start_m"])
                    eh, em = int(st["end_h"]), int(st["end_m"])

                    start_at = datetime(day.year, day.month, day.day, sh, sm, tzinfo=JST)
                    end_at = datetime(day.year, day.month, day.day, eh, em, tzinfo=JST)
                    if end_at <= start_at:
                        end_at += timedelta(days=1)

                    res = await self.dm.create_panel(
                        guild_id=str(interaction.guild_id),
                        channel_id=str(interaction.channel_id),
                        day_date=day,
                        title=st.get("title"),
                        start_at=start_at,
                        end_at=end_at,
                        interval_minutes=int(st["interval"]),
                        notify_channel_id=str(st["notify_channel_id"]),
                        created_by=str(interaction.user.id),
                        everyone=bool(st["everyone"]),
                    )

                    if not res.get("ok"):
                        await interaction.followup.send(f"❌ 作成失敗: {res.get('error','unknown')}", ephemeral=True)
                        await self._edit_setup_ephemeral(interaction)
                        return

                    await self.dm.render_panel(self, int(res["panel_id"]))
                    self.setup_state.pop(interaction.user.id, None)

                    try:
                        await interaction.edit_original_response(content="✅ 作成完了！", embed=None, view=None)
                    except Exception:
                        pass
                    return

                await self._edit_setup_ephemeral(interaction)
                return

            await safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            try:
                await interaction.followup.send(f"❌ エラー: {repr(e)}", ephemeral=True)
            except Exception:
                pass


async def runner_forever():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN 未設定")

    # ✅ 落ちたら “新しいClientを作り直す”
    while True:
        bot = MyClient()
        try:
            await bot.start(TOKEN)
        except Exception as e:
            print("🔥 FATAL crash -> restart:", repr(e))
            print(traceback.format_exc())
            try:
                if reminder_loop.is_running():
                    reminder_loop.stop()
            except Exception:
                pass
            try:
                await bot.close()
            except Exception:
                pass
            await asyncio.sleep(5)
        else:
            break


asyncio.run(runner_forever())