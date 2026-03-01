# bot_interact.py
from __future__ import annotations

import traceback
from datetime import datetime, timedelta
import discord

from utils.time_utils import jst_now
from views.setup_wizard import build_setup_embed, build_setup_view


# -----------------------------
# Setup Wizard State helpers
# -----------------------------
def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",            # ✅ デフォ今日（選ばなくてOK）
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,             # "HH:MM"
        "end": None,               # "HH:MM"
        "interval": None,          # int minutes
        "notify_channel_id": None, # str channel_id（選択式）
        "everyone": False,         # ✅ 作成時1回だけ @everyone
        "title": None,             # （setup_wizard側で入力UIがあれば使われる）
    }


def _ensure_setup_state(client: discord.Client, user_id: int) -> dict:
    if not hasattr(client, "setup_state") or client.setup_state is None:
        client.setup_state = {}

    st = client.setup_state.get(user_id)
    if not isinstance(st, dict):
        st = _default_setup_state()
        client.setup_state[user_id] = st

    base = _default_setup_state()
    for k, v in base.items():
        st.setdefault(k, v)

    if st.get("step") not in (1, 2):
        st["step"] = 1

    # day が None でも today 扱い
    if st.get("day") not in ("today", "tomorrow"):
        st["day"] = "today"

    return st


def _recalc_hm(st: dict):
    if st.get("start_hour") is not None and st.get("start_min") is not None:
        st["start"] = f"{int(st['start_hour']):02d}:{int(st['start_min']):02d}"
    else:
        st["start"] = None

    if st.get("end_hour") is not None and st.get("end_min") is not None:
        st["end"] = f"{int(st['end_hour']):02d}:{int(st['end_min']):02d}"
    else:
        st["end"] = None


def _parse_hm(hm: str) -> tuple[int, int] | None:
    try:
        h, m = hm.split(":")
        return int(h), int(m)
    except Exception:
        return None


def _build_day_date(day_key: str):
    now = jst_now()
    if day_key == "tomorrow":
        return (now + timedelta(days=1)).date()
    return now.date()


# -----------------------------
# Interaction safe helpers
# -----------------------------
async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    """
    ✅ component は bot_app.py 側で defer 済みが多い
    → followup 優先で返す（40060防止）
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_send_view(interaction: discord.Interaction, text: str, view: discord.ui.View):
    """
    ✅ View付きメッセージを安全に送る
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, view=view, ephemeral=True)
        else:
            await interaction.response.send_message(text, view=view, ephemeral=True)
    except Exception:
        pass


async def _safe_edit_message(interaction: discord.Interaction, *, embed=None, view=None, content=None):
    """
    ✅ 元メッセ（ウィザード）を編集して更新
    """
    try:
        if interaction.message:
            await interaction.message.edit(content=content, embed=embed, view=view)
            return
    except Exception:
        pass
    try:
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    except Exception:
        pass


# -----------------------------
# custom_id parsers (PanelView対応)
# -----------------------------
def _parse_panel_slot(custom_id: str) -> tuple[int, int] | None:
    # panel:slot:{panel_id}:{slot_id}
    if not custom_id.startswith("panel:slot:"):
        return None
    parts = custom_id.split(":")
    if len(parts) < 4:
        return None
    try:
        return int(parts[2]), int(parts[3])
    except Exception:
        return None


def _parse_breaktoggle(custom_id: str) -> int | None:
    # panel:breaktoggle:{panel_id}
    if not custom_id.startswith("panel:breaktoggle:"):
        return None
    parts = custom_id.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[2])
    except Exception:
        return None


def _parse_breakselect(custom_id: str) -> int | None:
    # panel:breakselect:{panel_id}
    if not custom_id.startswith("panel:breakselect:"):
        return None
    parts = custom_id.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[2])
    except Exception:
        return None


def _parse_notifytoggle(custom_id: str) -> int | None:
    # panel:notifytoggle:{panel_id}
    if not custom_id.startswith("panel:notifytoggle:"):
        return None
    parts = custom_id.split(":")
    if len(parts) < 3:
        return None
    try:
        return int(parts[2])
    except Exception:
        return None


# -----------------------------
# Setup Wizard Handler
# -----------------------------
async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    st = _ensure_setup_state(bot, interaction.user.id)

    data = interaction.data or {}
    custom_id = data.get("custom_id")
    values = data.get("values") or []

    # --- buttons
    if custom_id == "setup:day:today":
        st["day"] = "today"
    elif custom_id == "setup:day:tomorrow":
        st["day"] = "tomorrow"
    elif custom_id == "setup:everyone:toggle":
        st["everyone"] = not bool(st.get("everyone"))

    elif custom_id == "setup:step:next":
        _recalc_hm(st)
        # day はデフォ today なので、ここで未選択チェック不要
        if not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
        else:
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                await _safe_ephemeral(interaction, "❌ 時刻の形式が不正です。もう一度選び直してね")
            elif (eh[0], eh[1]) <= (sh[0], sh[1]):
                await _safe_ephemeral(interaction, "❌ 終了は開始より後にしてください（同じ/前は不可）")
            else:
                st["step"] = 2

    elif custom_id == "setup:step:back":
        st["step"] = 1

    elif custom_id == "setup:create":
        _recalc_hm(st)

        if not st.get("start") or not st.get("end"):
            st["step"] = 1
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
        elif not st.get("interval"):
            st["step"] = 2
            await _safe_ephemeral(interaction, "❌ 間隔（分）を選んでください")
        else:
            notify_channel_id = st.get("notify_channel_id") or str(interaction.channel_id)

            day_date = _build_day_date(st["day"])
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                st["step"] = 1
                await _safe_ephemeral(interaction, "❌ 時刻が不正です。Step1で選び直してね")
            else:
                tz = jst_now().tzinfo
                start_at = datetime(day_date.year, day_date.month, day_date.day, sh[0], sh[1], tzinfo=tz)
                end_at = datetime(day_date.year, day_date.month, day_date.day, eh[0], eh[1], tzinfo=tz)

                try:
                    res = await dm.create_panel(
                        guild_id=str(interaction.guild_id),
                        channel_id=str(interaction.channel_id),
                        day_date=day_date,
                        title=st.get("title"),
                        start_at=start_at,
                        end_at=end_at,
                        interval_minutes=int(st["interval"]),
                        notify_channel_id=str(notify_channel_id),
                        created_by=str(interaction.user.id),
                    )

                    if not res.get("ok"):
                        await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error', 'unknown')}")
                    else:
                        panel_id = int(res["panel_id"])
                        await dm.render_panel(bot, panel_id)

                        # ✅ @everyone は「作成時1回だけ」
                        if bool(st.get("everyone")):
                            try:
                                ch = interaction.channel or bot.get_channel(int(interaction.channel_id))
                                if ch:
                                    await ch.send("@everyone 募集を開始しました！")
                            except Exception:
                                pass

                        embed = discord.Embed(
                            title="✅ 作成しました",
                            description="パネルを投稿しました。",
                            color=0x57F287
                        )
                        await _safe_edit_message(interaction, embed=embed, view=None)
                        await _safe_ephemeral(interaction, "✅ 完了！パネルを確認してね")

                        try:
                            bot.setup_state.pop(interaction.user.id, None)
                        except Exception:
                            pass
                        return

                except Exception:
                    await _safe_ephemeral(interaction, "❌ 作成中にエラー（ログ確認）")
                    print("setup:create error")
                    print(traceback.format_exc())

    # --- selects
    elif custom_id == "setup:start_hour" and values:
        st["start_hour"] = values[0]
    elif custom_id == "setup:start_min" and values:
        st["start_min"] = values[0]
    elif custom_id == "setup:end_hour" and values:
        st["end_hour"] = values[0]
    elif custom_id == "setup:end_min" and values:
        st["end_min"] = values[0]
    elif custom_id == "setup:interval" and values:
        try:
            st["interval"] = int(values[0])
        except Exception:
            st["interval"] = None
    elif custom_id == "setup:notify_channel" and values:
        # ChannelSelect は values[0] が channel_id
        st["notify_channel_id"] = str(values[0])

    _recalc_hm(st)
    await _safe_edit_message(interaction, embed=build_setup_embed(st), view=build_setup_view(st))


# -----------------------------
# Panel Handlers
# -----------------------------
async def handle_panel_slot(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int, slot_id: int):
    ok, msg = await dm.toggle_reserve(
        slot_id=slot_id,
        user_id=str(interaction.user.id),
        user_name=getattr(interaction.user, "display_name", None) or interaction.user.name,
    )
    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)

    try:
        await dm.render_panel(bot, panel_id)
    except Exception:
        print("render_panel error")
        print(traceback.format_exc())


async def handle_notify_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return

    ok, msg = await dm.toggle_notify_paused(panel_id)
    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)

    try:
        await dm.render_panel(bot, panel_id)
    except Exception:
        print("render_panel error")
        print(traceback.format_exc())


async def handle_break_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return

    try:
        view = await dm.build_break_select_view(panel_id)
        # ✅ ここは followup 優先で送る（40060の元を断つ）
        await _safe_send_view(interaction, "🛠 休憩にする/解除する時間を選んでください", view=view)
    except Exception:
        print("breaktoggle error")
        print(traceback.format_exc())
        await _safe_ephemeral(interaction, "❌ 休憩選択の表示に失敗（ログ確認）")


async def handle_break_select(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int, slot_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return

    ok, msg = await dm.toggle_break_slot(panel_id=panel_id, slot_id=slot_id)
    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)

    try:
        await dm.render_panel(bot, panel_id)
    except Exception:
        print("render_panel error")
        print(traceback.format_exc())


# -----------------------------
# Entry point
# -----------------------------
async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    """
    bot_app.py の on_interaction(component) から呼ばれる入口
    """
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        if not custom_id:
            return

        dm = getattr(bot, "dm", None)
        if dm is None:
            await _safe_ephemeral(interaction, "❌ DataManager未初期化")
            return

        # ✅ setup wizard
        if custom_id.startswith("setup:"):
            await handle_setup_wizard(bot, interaction, dm)
            return

        # ✅ パネル：枠ボタン
        ps = _parse_panel_slot(custom_id)
        if ps:
            panel_id, slot_id = ps
            await handle_panel_slot(bot, interaction, dm, panel_id, slot_id)
            return

        # ✅ 通知 ON/OFF
        panel_id = _parse_notifytoggle(custom_id)
        if panel_id is not None:
            await handle_notify_toggle(bot, interaction, dm, panel_id)
            return

        # ✅ 休憩切替
        panel_id = _parse_breaktoggle(custom_id)
        if panel_id is not None:
            await handle_break_toggle(bot, interaction, dm, panel_id)
            return

        # ✅ 休憩 select
        panel_id = _parse_breakselect(custom_id)
        if panel_id is not None:
            values = (data.get("values") or [])
            if not values:
                return
            try:
                slot_id = int(values[0])
            except Exception:
                await _safe_ephemeral(interaction, "❌ 選択値が不正です")
                return
            await handle_break_select(bot, interaction, dm, panel_id, slot_id)
            return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass