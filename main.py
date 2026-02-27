# main.py  （B方式 + setup wizard + “アプリ反応しません”対策）
print("🔥 BOOT MARKER v2026-02-27 B-mode stable FINAL COMPLETE (FULL COPY) 🔥")

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

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")

intents = discord.Intents.default()


# ------------------------------
# 共通ユーティリティ
# ------------------------------
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


async def safe_send(interaction: discord.Interaction, content: str | None = None, *, embed=None, view=None, ephemeral: bool = True):
    """二重返信でも落ちない送信。"""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content=content, embed=embed, view=view, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content=content, embed=embed, view=view, ephemeral=ephemeral)
    except Exception:
        pass


# ------------------------------
# Bot本体
# ------------------------------
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # reminderバックオフ（Session is closed 対策）
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0  # loop.time()

        # setupウィザード状態（ユーザーごと）
        self.setup_state: dict[int, dict] = {}

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

    async def _dispatch_tree(self, interaction: discord.Interaction):
        """
        discord.py版差対策:
        tree._from_interaction が coroutine の版と、None返す版がある
        """
        try:
            res = self.tree._from_interaction(interaction)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            # ここで落としてbot止めない
            pass

    async def _refresh_setup(self, interaction: discord.Interaction):
        from views.setup_wizard import build_setup_embed, build_setup_view

        st = self.dm.get_or_init_setup_state(self.setup_state, interaction.user.id)
        embed = build_setup_embed(st)
        view = build_setup_view(st)

        try:
            # wizardは /setup_channel の followup で送った “そのメッセージ” を編集する
            if interaction.message:
                await interaction.message.edit(embed=embed, view=view)
        except Exception:
            pass

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 安定版:
        - スラッシュ/モーダル送信は tree へ（ただしモーダルはここで拾う）
        - component(ボタン/セレクト) はここで処理
        """
        try:
            # -------------------------
            # 0) モーダル送信（タイトル入力）
            # -------------------------
            if interaction.type == discord.InteractionType.modal_submit:
                await safe_defer(interaction, ephemeral=True)
                if interaction.data and interaction.data.get("custom_id") == "setup:title_modal":
                    st = self.dm.get_or_init_setup_state(self.setup_state, interaction.user.id)
                    # components[0][0].value
                    try:
                        comps = interaction.data.get("components") or []
                        val = comps[0]["components"][0].get("value")
                        st["title"] = (val or "").strip() or None
                    except Exception:
                        pass

                    await self._refresh_setup(interaction)
                    await safe_send(interaction, "✅ タイトルを更新したよ", ephemeral=True)
                    return

                # それ以外のモーダルは無視（treeに任せたいならここでdispatch）
                await safe_send(interaction, "❌ 未対応モーダルです", ephemeral=True)
                return

            # -------------------------
            # 1) component以外は tree に渡す（スラッシュ等）
            # -------------------------
            if interaction.type != discord.InteractionType.component:
                await self._dispatch_tree(interaction)
                return

            # -------------------------
            # 2) component（ボタン/セレクト）
            # -------------------------
            data = interaction.data or {}
            custom_id = data.get("custom_id")
            values = data.get("values") or []

            if not custom_id or not isinstance(custom_id, str):
                return

            # 3秒対策（ボタン/セレクトも必ず即defer）
            await safe_defer(interaction, ephemeral=True)

            # -----------------------------
            # panel処理（予約ボタン等）
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

                # defer済みなので followup
                try:
                    await interaction.followup.send(
                        "⌚️ 休憩にする/解除する時間を選んでね👇",
                        view=view,
                        ephemeral=True,
                    )
                except Exception:
                    await safe_send(interaction, "❌ 表示に失敗しました（もう一度押して）", ephemeral=True)
                return

            if custom_id.startswith("panel:breakselect:"):
                if not _is_admin(interaction):
                    await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                    return

                parts = custom_id.split(":")
                if len(parts) != 3:
                    await safe_send(interaction, "❌ セレクト形式が不正です", ephemeral=True)
                    return

                panel_id = int(parts[2])
                if not values:
                    await safe_send(interaction, "❌ 選択値が取得できませんでした", ephemeral=True)
                    return

                slot_id = int(values[0])

                ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
                await self.dm.render_panel(self, panel_id)
                await safe_send(interaction, msg, ephemeral=True)
                return

            # -----------------------------
            # setupウィザード（画像みたいなUI）
            # 必須:
            #  - 今日/明日
            #  - 開始時刻/終了時刻
            #  - 間隔(20/25/30)
            #  - 通知チャンネル
            # 任意:
            #  - everyone
            #  - タイトル（モーダル）
            # -----------------------------
            if custom_id.startswith("setup:"):
                st = self.dm.get_or_init_setup_state(self.setup_state, interaction.user.id)

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
                    st["everyone"] = not bool(st.get("everyone", False))

                elif custom_id == "setup:title:open":
                    # モーダル開く（defer後でもOK。discord.pyが裏で処理するのでtry）
                    try:
                        modal = discord.ui.Modal(title="タイトル入力", custom_id="setup:title_modal")
                        modal.add_item(discord.ui.TextInput(
                            label="タイトル（空で未設定）",
                            required=False,
                            max_length=50,
                            placeholder="例：夜の部 / Aチーム など",
                            default=st.get("title") or "",
                        ))
                        await interaction.response.send_modal(modal)
                        return
                    except Exception:
                        # defer済みなので followupで案内
                        await safe_send(interaction, "❌ タイトル入力の表示に失敗した…もう一度押して", ephemeral=True)
                        return

                # 時刻確定
                if st.get("start_hour") and st.get("start_min"):
                    st["start"] = f"{st['start_hour']}:{st['start_min']}"
                if st.get("end_hour") and st.get("end_min"):
                    st["end"] = f"{st['end_hour']}:{st['end_min']}"

                # 作成
                if custom_id == "setup:create":
                    missing = []
                    if not st.get("day"):
                        missing.append("今日/明日")
                    if not st.get("start"):
                        missing.append("開始時刻")
                    if not st.get("end"):
                        missing.append("終了時刻")
                    if not st.get("interval"):
                        missing.append("間隔(20/25/30)")
                    if not st.get("notify_channel_id"):
                        missing.append("通知チャンネル")

                    if missing:
                        await safe_send(interaction, "❌ 未入力: " + " / ".join(missing), ephemeral=True)
                        await self._refresh_setup(interaction)
                        return

                    JST = timezone(timedelta(hours=9))
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
                        mention_everyone=bool(st.get("everyone", False)),
                    )

                    if not res.get("ok"):
                        await safe_send(interaction, f"❌ 作成失敗: {res.get('error','unknown')}", ephemeral=True)
                        await self._refresh_setup(interaction)
                        return

                    await self.dm.render_panel(self, int(res["panel_id"]))
                    self.setup_state.pop(interaction.user.id, None)
                    await safe_send(interaction, "✅ 作成完了", ephemeral=True)
                    return

                # 画面更新
                await self._refresh_setup(interaction)
                await safe_send(interaction, "✅ 更新", ephemeral=True)
                return

            # 想定外
            await safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

        except Exception as e:
            print("on_interaction error:", repr(e))
            print(traceback.format_exc())
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)


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

        # backoff: 60,120,240... max 600
        backoff = min(600, 60 * (2 ** (bot._reminder_fail_count - 1)))
        msg = repr(e)
        if "Session is closed" in msg:
            backoff = max(backoff, 120)

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