# main.py  完全版（B方式：custom_id を main.py で処理 / 落ちない / ウィザード付き）
print("🔥 BOOT MARKER v2026-02-27 COMPLETE STABLE WIZARD 🔥")

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

from views.setup_wizard import build_setup_embed, build_setup_view, TitleModal


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


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    """3秒制限回避（既に応答済みなら何もしない）"""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    """二重返信でも落ちない送信"""
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

        # reminderバックオフ
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0

        # setupウィザード状態（ユーザーごと）
        self.setup_state: dict[int, dict] = {}

    async def setup_hook(self):
        register_setup(self.tree, self)
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

    # ---------- setup wizard state ----------
    def get_setup_state(self, user_id: int) -> dict:
        st = self.setup_state.get(user_id)
        if st is None:
            st = {
                "day": None,                # "today" or "tomorrow"
                "start_hour": None,
                "start_min": None,
                "end_hour": None,
                "end_min": None,
                "interval": None,           # 20/25/30
                "notify_channel_id": None,  # required
                "everyone": False,          # optional
                "title": None,              # optional
            }
            self.setup_state[user_id] = st
        return st

    def clear_setup_state(self, user_id: int):
        self.setup_state.pop(user_id, None)

    def state_to_timestr(self, st: dict) -> tuple[str | None, str | None]:
        start = None
        end = None
        if st.get("start_hour") is not None and st.get("start_min") is not None:
            start = f"{st['start_hour']}:{st['start_min']}"
        if st.get("end_hour") is not None and st.get("end_min") is not None:
            end = f"{st['end_hour']}:{st['end_min']}"
        return start, end

    async def refresh_setup_message(self, message: discord.Message, st: dict):
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        try:
            await message.edit(embed=embed, view=view)
        except Exception:
            pass

    async def start_setup_wizard(self, interaction: discord.Interaction):
        """/setup_channel から呼ばれる。画像みたいに 今日/明日 を出す"""
        st = self.get_setup_state(interaction.user.id)
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ---------- main interaction dispatcher ----------
    async def _dispatch_tree(self, interaction: discord.Interaction):
        """スラッシュ等は tree に渡す"""
        try:
            res = self.tree._from_interaction(interaction)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # component以外はtreeへ
            if interaction.type != discord.InteractionType.component:
                await self._dispatch_tree(interaction)
                return

            data = interaction.data or {}
            custom_id = data.get("custom_id")
            values = data.get("values") or []
            if not custom_id:
                return

            # ✅ まず defer（これが「反応しません」対策）
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
            # panel（休憩トグル）
            # -----------------------------
            if custom_id.startswith("panel:breaktoggle:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます")
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await safe_send(interaction, "❌ ボタン形式が不正です")
                    return
                panel_id = int(parts[2])

                view = await self.dm.build_break_select_view(panel_id)
                try:
                    await interaction.followup.send(
                        "⌚️ 休憩にする/解除する時間を選んでね👇",
                        view=view,
                        ephemeral=True,
                    )
                except Exception:
                    await safe_send(interaction, "❌ 表示に失敗しました（もう一度押して）")
                return

            if custom_id.startswith("panel:breakselect:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます")
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await safe_send(interaction, "❌ セレクト形式が不正です")
                    return
                panel_id = int(parts[2])

                if not values:
                    await safe_send(interaction, "❌ 選択値が取得できませんでした")
                    return
                slot_id = int(values[0])

                ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg)
                return

            # -----------------------------
            # setup wizard（画像のやつ）
            # -----------------------------
            if custom_id.startswith("setup:"):
                st = self.get_setup_state(interaction.user.id)

                # 押したメッセージを編集するので message 必須
                msg_obj = interaction.message
                if msg_obj is None:
                    await safe_send(interaction, "❌ メッセージが取得できませんでした（もう一度 /setup_channel）")
                    return

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
                    # ChannelSelect は value が channel_id
                    st["notify_channel_id"] = str(values[0])

                elif custom_id == "setup:everyone:toggle":
                    st["everyone"] = not st["everyone"]

                elif custom_id == "setup:title:open":
                    # Modal（タイトル入力）
                    try:
                        await interaction.response.send_modal(TitleModal(self, st, msg_obj))
                    except Exception:
                        # defer済みなので followup で案内
                        await safe_send(interaction, "❌ タイトル入力を開けませんでした（discord.py更新が必要かも）")
                    return

                elif custom_id == "setup:cancel":
                    self.clear_setup_state(interaction.user.id)
                    try:
                        await msg_obj.edit(content="✅ キャンセルしました", embed=None, view=None)
                    except Exception:
                        pass
                    return

                elif custom_id == "setup:create":
                    start, end = self.state_to_timestr(st)

                    missing = []
                    if not st.get("day"):
                        missing.append("今日/明日")
                    if not start:
                        missing.append("開始時刻")
                    if not end:
                        missing.append("終了時刻")
                    if not st.get("interval"):
                        missing.append("間隔(20/25/30)")
                    if not st.get("notify_channel_id"):
                        missing.append("通知チャンネル")

                    if missing:
                        await safe_send(interaction, "❌ 未入力: " + " / ".join(missing))
                        await self.refresh_setup_message(msg_obj, st)
                        return

                    today = datetime.now(JST).date()
                    day = today if st["day"] == "today" else today + timedelta(days=1)

                    sh, sm = map(int, start.split(":"))
                    eh, em = map(int, end.split(":"))

                    start_at = datetime(day.year, day.month, day.day, sh, sm, tzinfo=JST)
                    end_at = datetime(day.year, day.month, day.day, eh, em, tzinfo=JST)
                    if end_at <= start_at:
                        end_at += timedelta(days=1)

                    # ここでDB作成（時間かかっても defer 済みなのでOK）
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
                        mention_everyone=bool(st.get("everyone", False)),
                    )

                    if not res.get("ok"):
                        await safe_send(interaction, f"❌ 作成失敗: {res.get('error','unknown')}")
                        await self.refresh_setup_message(msg_obj, st)
                        return

                    await self.dm.render_panel(self, int(res["panel_id"]))
                    self.clear_setup_state(interaction.user.id)

                    try:
                        await msg_obj.edit(content="✅ 作成完了", embed=None, view=None)
                    except Exception:
                        pass

                    await safe_send(interaction, "✅ パネルを作成しました")
                    return

                # 通常更新
                await self.refresh_setup_message(msg_obj, st)
                await safe_send(interaction, "✅ 更新")
                return

            # 想定外
            await safe_send(interaction, f"unknown custom_id: {custom_id}")

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            await safe_send(interaction, f"❌ エラー: {repr(e)}")


client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
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


@reminder_loop.before_loop
async def before_reminder_loop():
    await client.wait_until_ready()
    await asyncio.sleep(5)

    host = supabase_host_from_url(SUPABASE_URL)
    if host:
        try:
            ip = socket.gethostbyname(host)
            print(f"✅ DNS check OK: {host} -> {ip}")
        except Exception as e:
            print("⚠️ DNS check failed:", repr(e))


async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN 未設定")

    # ✅ Renderで「落ちる」を防ぐ：例外が出てもプロセスは生きてリトライ
    while True:
        try:
            await client.start(TOKEN)
            return
        except Exception as e:
            print("🔥 client.start failed:", repr(e))
            print(traceback.format_exc())
            try:
                await client.close()
            except Exception:
                pass
            await asyncio.sleep(10)


asyncio.run(main())