# main.py（STABLE RUN MODE + "Application did not respond"対策）
print("🔥 BOOT MARKER v2026-02-27 STABLE RUN MODE + RESP FIX 🔥")

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

TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip()

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


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    # 3秒制限回避（component用）
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
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

        # setupウィザード状態（ユーザーごと）
        self.setup_state: dict[int, dict] = {}

        async def setup_hook(self):
            register_setup(self.tree, self.dm)
            register_reset(self.tree, self.dm)
            register_remind(self.tree, self.dm)
            register_notify(self.tree, self.dm)
            register_notify_panel(self.tree, self.dm)
            register_manager_role(self.tree, self.dm)

        # ✅ 追加：スラッシュコマンドの例外を必ずログ＆返信する（超重要）
        @self.tree.error
        async def on_app_command_error(interaction: discord.Interaction, error: Exception):
            # CommandInvokeError の中身（元の例外）を取り出す
            original = getattr(error, "original", None)

            print("❌ APP_COMMAND_ERROR:", repr(error))
            if original:
                print("❌ ORIGINAL:", repr(original))
            print(traceback.format_exc())

            # 3秒で「反応しません」にならないよう、できるだけ返す
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        f"❌ コマンドエラー: {type(original or error).__name__}\n{repr(original or error)}",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"❌ コマンドエラー: {type(original or error).__name__}\n{repr(original or error)}",
                        ephemeral=True
                    )
            except Exception:
                pass

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # ✅ ここが重要：スラッシュは公式APIで処理
            if interaction.type == discord.InteractionType.application_command:
                await self.tree.process_interaction(interaction)
                return

            # component以外は無視
            if interaction.type != discord.InteractionType.component:
                return

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            values = data.get("values") or []

            if not custom_id or not isinstance(custom_id, str):
                return

            # componentは先にdefer（3秒対策）
            await safe_defer(interaction, ephemeral=True)

            # -----------------------------
            # panel（予約ボタン）
            # -----------------------------
            if custom_id.startswith("panel:slot:"):
                parts = custom_id.split(":")
                if len(parts) != 4:
                    await safe_send(interaction, "❌ ボタン形式が不正です")
                    return

                panel_id = int(parts[2])
                slot_id = int(parts[3])

                ok, msg = await self.dm.toggle_reserve(
                    slot_id=slot_id,
                    user_id=str(interaction.user.id),
                    user_name=getattr(interaction.user, "display_name", str(interaction.user)),
                )
                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg)
                return

            # -----------------------------
            # setupウィザード
            # -----------------------------
            if custom_id.startswith("setup:"):
                st = self._get_setup_state(interaction.user.id)

                if custom_id == "setup:day:today":
                    st["day"] = "today"
                elif custom_id == "setup:day:tomorrow":
                    st["day"] = "tomorrow"

                elif custom_id == "setup:start_hour" and values:
                    st["start_hour"] = values[0]
                elif custom_id == "setup:start_min" and values:
                    st["start_min"] = values[0]
                elif custom_id == "setup:end_hour" and values:
                    st["end_hour"] = values[0]
                elif custom_id == "setup:end_min" and values:
                    st["end_min"] = values[0]

                elif custom_id.startswith("setup:interval:"):
                    st["interval"] = int(custom_id.split(":")[-1])

                elif custom_id == "setup:notify_channel" and values:
                    st["notify_channel_id"] = str(values[0])

                elif custom_id == "setup:everyone:toggle":
                    st["everyone"] = not st["everyone"]

                # 表示用まとめ
                if st.get("start_hour") and st.get("start_min"):
                    st["start"] = f"{st['start_hour']}:{st['start_min']}"
                if st.get("end_hour") and st.get("end_min"):
                    st["end"] = f"{st['end_hour']}:{st['end_min']}"

                # 作成
                if custom_id == "setup:create":
                    missing = []
                    if not st.get("day"): missing.append("今日/明日")
                    if not st.get("start"): missing.append("開始")
                    if not st.get("end"): missing.append("終了")
                    if not st.get("interval"): missing.append("間隔")
                    if not st.get("notify_channel_id"): missing.append("通知チャンネル")

                    if missing:
                        await safe_send(interaction, "❌ 未入力: " + " / ".join(missing))
                        await self._refresh_setup(interaction)
                        return

                    today = datetime.now(JST).date()
                    day = today if st["day"] == "today" else today + timedelta(days=1)

                    sh, sm = map(int, st["start"].split(":"))
                    eh, em = map(int, st["end"].split(":"))

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
                    )

                    if not res.get("ok"):
                        await safe_send(interaction, f"❌ 作成失敗: {res.get('error','unknown')}")
                        await self._refresh_setup(interaction)
                        return

                    await self.dm.render_panel(self, int(res["panel_id"]))
                    self.setup_state.pop(interaction.user.id, None)
                    await safe_send(interaction, "✅ 作成完了")
                    return

                await self._refresh_setup(interaction)
                await safe_send(interaction, "✅ 更新")
                return

            await safe_send(interaction, f"unknown custom_id: {custom_id}")

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            try:
                await safe_send(interaction, f"❌ エラー: {repr(e)}")
            except Exception:
                pass


client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    if not bot.is_ready() or bot.is_closed():
        return
    try:
        await bot.dm.send_3min_reminders(bot)
    except Exception as e:
        print("reminder_loop error:", repr(e))


@reminder_loop.before_loop
async def before_reminder_loop():
    await client.wait_until_ready()
    await asyncio_sleep(5)

    host = supabase_host_from_url(SUPABASE_URL)
    if host:
        try:
            ip = socket.gethostbyname(host)
            print(f"✅ DNS check OK: {host} -> {ip}")
        except Exception as e:
            print("⚠️ DNS check failed:", repr(e))


async def asyncio_sleep(sec: int):
    # discord.pyが動いてるloop内で安全にsleep
    await discord.utils.sleep_until(discord.utils.utcnow() + timedelta(seconds=sec))


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定（RenderのEnvironmentを確認）")
    client.run(TOKEN)