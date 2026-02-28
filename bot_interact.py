# bot_interact.py
from __future__ import annotations

import asyncio
import re
import traceback
from datetime import datetime, timedelta

import discord

from utils.time_utils import jst_now
from utils.db import sb
from views.setup_wizard import build_setup_embed, build_setup_view


# -----------------------------
# Setup Wizard State helpers
# -----------------------------
def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": None,               # "today" | "tomorrow"
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,             # "HH:MM"
        "end": None,               # "HH:MM"
        "interval": None,          # int minutes
        "notify_channel_id": None, # str channel_id
        "everyone": False,
        "title": None,
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

    return st


def _recalc_hm(st: dict):
    if st.get("start_hour") is not None and st.get("start_min") is not None:
        st["start"] = f"{int(st['start_hour']):02d}:{int(st['start_min']):02d}"
    else:
        st["start"] = st.get("start") or None

    if st.get("end_hour") is not None and st.get("end_min") is not None:
        st["end"] = f"{int(st['end_hour']):02d}:{int(st['end_min']):02d}"
    else:
        st["end"] = st.get("end") or None


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


async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_edit_message(interaction: discord.Interaction, *, embed=None, view=None, content=None):
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
# DB helpers for panel buttons
# -----------------------------
async def _db(fn):
    return await asyncio.to_thread(fn)


async def _get_panel_id_by_slot_id(slot_id: int) -> int | None:
    # slots.id -> panel_id を引く
    def work():
        rows = (
            sb.table("slots")
            .select("panel_id")
            .eq("id", slot_id)
            .limit(1)
            .execute()
            .data
            or []
        )
        if not rows:
            return None
        return int(rows[0]["panel_id"])

    try:
        return await _db(work)
    except Exception:
        return None


def _extract_slot_id(custom_id: str) -> int | None:
    """
    いろんな形式に対応:
    - "slot:123"
    - "reserve:123"
    - "panel:slot:123"
    - "123"（数字だけ）
    - "slot_123" / "slot-123"
    """
    if not custom_id:
        return None

    # 数字だけ
    if custom_id.isdigit():
        return int(custom_id)

    m = re.search(r"(\d{1,12})", custom_id)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


# -----------------------------
# Setup Wizard Handler
# -----------------------------
async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    user_id = interaction.user.id
    st = _ensure_setup_state(bot, user_id)

    data = interaction.data or {}
    custom_id = data.get("custom_id")
    values = data.get("values") or []

    if custom_id == "setup:day:today":
        st["day"] = "today"
    elif custom_id == "setup:day:tomorrow":
        st["day"] = "tomorrow"
    elif custom_id == "setup:everyone:toggle":
        st["everyone"] = not bool(st.get("everyone"))

    elif custom_id == "setup:step:next":
        _recalc_hm(st)
        if st.get("day") not in ("today", "tomorrow"):
            await _safe_ephemeral(interaction, "❌ 日付（今日/明日）を選んでください")
        elif not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
        else:
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                await _safe_ephemeral(interaction, "❌ 時刻の形式が不正です。もう一度選び直してね")
            else:
                if (eh[0], eh[1]) <= (sh[0], sh[1]):
                    await _safe_ephemeral(interaction, "❌ 終了は開始より後にしてください（同じ/前は不可）")
                else:
                    st["step"] = 2

    elif custom_id == "setup:step:back":
        st["step"] = 1

    elif custom_id == "setup:create":
        _recalc_hm(st)

        if st.get("day") not in ("today", "tomorrow"):
            await _safe_ephemeral(interaction, "❌ 日付（今日/明日）を選んでください")
            st["step"] = 1
        elif not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
            st["step"] = 1
        elif not st.get("interval"):
            await _safe_ephemeral(interaction, "❌ 間隔（分）を選んでください")
            st["step"] = 2
        else:
            notify_channel_id = st.get("notify_channel_id") or str(interaction.channel_id)

            day_date = _build_day_date(st["day"])
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                await _safe_ephemeral(interaction, "❌ 時刻が不正です。Step1で選び直してね")
                st["step"] = 1
            else:
                start_at = datetime(day_date.year, day_date.month, day_date.day, sh[0], sh[1], tzinfo=jst_now().tzinfo)
                end_at = datetime(day_date.year, day_date.month, day_date.day, eh[0], eh[1], tzinfo=jst_now().tzinfo)

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

                        embed = discord.Embed(title="✅ 作成しました", description="パネルを投稿しました。", color=0x57F287)
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

    # selects
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
        st["notify_channel_id"] = str(values[0])

    _recalc_hm(st)
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    await _safe_edit_message(interaction, embed=embed, view=view)


# -----------------------------
# Panel reserve handler
# -----------------------------
async def handle_panel_reserve(bot: discord.Client, interaction: discord.Interaction, dm, custom_id: str):
    """
    PanelViewのボタンを押したときに予約/キャンセルする
    """
    if sb is None:
        await _safe_ephemeral(interaction, "❌ DB未接続（SUPABASE設定を確認）")
        return

    slot_id = _extract_slot_id(custom_id)
    if not slot_id:
        # 何もしない（別のViewのボタンかも）
        return

    # 予約トグル
    ok, msg = await dm.toggle_reserve(
        slot_id=slot_id,
        user_id=str(interaction.user.id),
        user_name=getattr(interaction.user, "display_name", None) or interaction.user.name,
    )

    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)

    # パネル更新（slot_id→panel_id引いて再描画）
    panel_id = await _get_panel_id_by_slot_id(slot_id)
    if not panel_id:
        return
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
        if custom_id.startswith("setup:") or custom_id.startswith("setup"):
            await handle_setup_wizard(bot, interaction, dm)
            return

        # ✅ 募集パネル（予約ボタン）: custom_idに数字が含まれていればslot_idとして扱う
        # （あなたのPanelViewのcustom_id形式が不明でも、ほぼ救えるようにしてある）
        await handle_panel_reserve(bot, interaction, dm, custom_id)
        return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass