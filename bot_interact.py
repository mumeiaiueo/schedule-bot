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
from views.panel_view import BreakSelectView


# -----------------------------
# Setup Wizard State helpers
# -----------------------------
def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",            # default today
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,
        "end": None,
        "interval": None,          # 20/25/30
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


# componentは defer済み前提 → followupだけ使う
async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        await interaction.followup.send(text, ephemeral=True)
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
# DB helpers
# -----------------------------
async def _db(fn):
    return await asyncio.to_thread(fn)


def _extract_panel_slot(custom_id: str) -> tuple[int, int] | None:
    # panel:slot:<panel_id>:<slot_id>
    m = re.match(r"^panel:slot:(\d+):(\d+)$", custom_id or "")
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _extract_panel_id(custom_id: str, prefix: str) -> int | None:
    # panel:notifytoggle:<panel_id> / panel:breaktoggle:<panel_id> / panel:breakselect:<panel_id>
    m = re.match(rf"^{re.escape(prefix)}:(\d+)$", custom_id or "")
    if not m:
        return None
    return int(m.group(1))


async def _get_panel_id_by_slot_id(slot_id: int) -> int | None:
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


# -----------------------------
# Setup Wizard Handler
# -----------------------------
async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    user_id = interaction.user.id
    st = _ensure_setup_state(bot, user_id)

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
        if not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
        else:
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                await _safe_ephemeral(interaction, "❌ 時刻が不正です。もう一度選んでね")
            elif (eh[0], eh[1]) <= (sh[0], sh[1]):
                await _safe_ephemeral(interaction, "❌ 終了は開始より後にしてください")
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
            await _safe_ephemeral(interaction, "❌ 間隔（20/25/30）を選んでください")
        else:
            day_date = _build_day_date(st.get("day", "today"))
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
                        created_by=str(interaction.user.id),
                        everyone=bool(st.get("everyone", False)),  # ✅ missing防止
                    )
                except Exception:
                    print("setup:create error")
                    print(traceback.format_exc())
                    await _safe_ephemeral(interaction, "❌ 作成中にエラー（ログ確認）")
                    res = {"ok": False}

                if not res.get("ok"):
                    await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error', 'unknown')}")
                else:
                    panel_id = int(res["panel_id"])
                    await dm.render_panel(bot, panel_id)

                    # ✅ @everyone は作成時1回だけ（ONの時だけ）
                    if bool(st.get("everyone")):
                        try:
                            ch = bot.get_channel(int(interaction.channel_id))
                            if ch:
                                await ch.send("@everyone 募集を開始しました！")
                        except Exception:
                            pass

                    embed = discord.Embed(title="✅ 作成しました", description="パネルを投稿しました。", color=0x57F287)
                    await _safe_edit_message(interaction, embed=embed, view=None)
                    await _safe_ephemeral(interaction, "✅ 完了！パネルを確認してね")

                    try:
                        bot.setup_state.pop(interaction.user.id, None)
                    except Exception:
                        pass
                    return

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

    _recalc_hm(st)
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    await _safe_edit_message(interaction, embed=embed, view=view)


# -----------------------------
# Panel handlers
# -----------------------------
async def handle_panel_slot(bot: discord.Client, interaction: discord.Interaction, dm, custom_id: str):
    if sb is None:
        await _safe_ephemeral(interaction, "❌ DB未接続（SUPABASE設定を確認）")
        return

    parsed = _extract_panel_slot(custom_id)
    if not parsed:
        return
    panel_id, slot_id = parsed

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


async def handle_panel_break_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return

    view = await dm.build_break_select_view(panel_id)
    await _safe_ephemeral(interaction, "休憩にする/解除する時間を選んでください",)
    # followupでview付き送信（ephemeral）
    try:
        await interaction.followup.send("👇 休憩枠を選択", view=view, ephemeral=True)
    except Exception:
        pass


async def handle_panel_break_select(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int, values):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return
    if not values:
        return
    try:
        slot_id = int(values[0])
    except Exception:
        return

    ok, msg = await dm.toggle_break_slot(panel_id, slot_id)
    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)
    try:
        await dm.render_panel(bot, panel_id)
    except Exception:
        print("render_panel error")
        print(traceback.format_exc())


async def handle_panel_notify_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return
    try:
        new_paused = await dm.toggle_notify_paused(panel_id)
        await _safe_ephemeral(interaction, "✅ 通知をOFFにしました" if new_paused else "✅ 通知をONにしました")
        await dm.render_panel(bot, panel_id)
    except Exception:
        print("notifytoggle error")
        print(traceback.format_exc())
        await _safe_ephemeral(interaction, "❌ 通知切替でエラー（ログ確認）")


# -----------------------------
# Entry point
# -----------------------------
async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []
        if not custom_id:
            return

        dm = getattr(bot, "dm", None)
        if dm is None:
            await _safe_ephemeral(interaction, "❌ DataManager未初期化")
            return

        # setup wizard
        if custom_id.startswith("setup:"):
            await handle_setup_wizard(bot, interaction, dm)
            return

        # panel buttons
        if custom_id.startswith("panel:slot:"):
            await handle_panel_slot(bot, interaction, dm, custom_id)
            return

        if custom_id.startswith("panel:breaktoggle:"):
            panel_id = _extract_panel_id(custom_id, "panel:breaktoggle")
            if panel_id:
                await handle_panel_break_toggle(bot, interaction, dm, panel_id)
            return

        if custom_id.startswith("panel:breakselect:"):
            panel_id = _extract_panel_id(custom_id, "panel:breakselect")
            if panel_id:
                await handle_panel_break_select(bot, interaction, dm, panel_id, values)
            return

        if custom_id.startswith("panel:notifytoggle:"):
            panel_id = _extract_panel_id(custom_id, "panel:notifytoggle")
            if panel_id:
                await handle_panel_notify_toggle(bot, interaction, dm, panel_id)
            return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass