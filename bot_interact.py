# bot_interact.py
from __future__ import annotations

import traceback
from datetime import datetime, timedelta

import discord

from utils.time_utils import jst_now
from views.setup_wizard import (
    build_setup_embed,
    build_setup_view,
    TitleModal,
)


# =============================
# setup state
# =============================

def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,
        "end": None,
        "interval": None,
        "notify_channel_id": None,
        "everyone": False,
        "title": None,
    }


def _ensure_setup_state(client: discord.Client, user_id: int) -> dict:
    if not hasattr(client, "setup_state"):
        client.setup_state = {}

    st = client.setup_state.get(user_id)
    if not isinstance(st, dict):
        st = _default_setup_state()
        client.setup_state[user_id] = st

    base = _default_setup_state()
    for k, v in base.items():
        st.setdefault(k, v)

    return st


def _recalc_hm(st: dict):
    if st["start_hour"] and st["start_min"]:
        st["start"] = f"{int(st['start_hour']):02d}:{int(st['start_min']):02d}"
    else:
        st["start"] = None

    if st["end_hour"] and st["end_min"]:
        st["end"] = f"{int(st['end_hour']):02d}:{int(st['end_min']):02d}"
    else:
        st["end"] = None


def _parse_hm(hm: str):
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


# =============================
# safe helpers
# =============================

async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_edit(interaction: discord.Interaction, embed=None, view=None):
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        elif interaction.message:
            await interaction.message.edit(embed=embed, view=view)
    except Exception:
        pass


def _extract_modal_value(interaction: discord.Interaction) -> str:
    try:
        comps = interaction.data.get("components", [])
        for row in comps:
            for c in row.get("components", []):
                if "value" in c:
                    return str(c["value"]).strip()
    except Exception:
        pass
    return ""


# =============================
# setup handler
# =============================

async def handle_setup(bot: discord.Client, interaction: discord.Interaction, dm):

    user_id = interaction.user.id
    st = _ensure_setup_state(bot, user_id)

    # ----- modal submit -----
    if interaction.type == discord.InteractionType.modal_submit:
        if interaction.data.get("custom_id") == "setup:titlemodal":
            title = _extract_modal_value(interaction)
            st["title"] = title or None
            await _safe_ephemeral(
                interaction,
                f"✅ タイトル設定: {st['title'] or '未設定'}"
            )
        return

    # ----- component -----
    cid = interaction.data.get("custom_id")
    values = interaction.data.get("values") or []

    if cid == "setup:day:today":
        st["day"] = "today"

    elif cid == "setup:day:tomorrow":
        st["day"] = "tomorrow"

    elif cid == "setup:everyone:toggle":
        st["everyone"] = not st["everyone"]

    elif cid == "setup:step:next":
        _recalc_hm(st)
        if not st["start"] or not st["end"]:
            await _safe_ephemeral(interaction, "❌ 時刻を選んでください")
        else:
            st["step"] = 2

    elif cid == "setup:step:back":
        st["step"] = 1

    elif cid == "setup:title:open":
        await interaction.response.send_modal(
            TitleModal(current=st.get("title"))
        )
        return

    elif cid == "setup:create":

        _recalc_hm(st)

        if not st["start"] or not st["end"]:
            await _safe_ephemeral(interaction, "❌ 時刻未設定")
            return

        if not st["interval"]:
            await _safe_ephemeral(interaction, "❌ 間隔未設定")
            return

        if not st["notify_channel_id"]:
            await _safe_ephemeral(interaction, "❌ 通知チャンネル必須")
            return

        sh = _parse_hm(st["start"])
        eh = _parse_hm(st["end"])
        day_date = _build_day_date(st["day"])

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
                notify_channel_id=str(st["notify_channel_id"]),
                created_by=str(interaction.user.id),
            )

            if not res.get("ok"):
                await _safe_ephemeral(interaction, "❌ 作成失敗")
                return

            panel_id = int(res["panel_id"])
            await dm.render_panel(bot, panel_id)

            await _safe_edit(
                interaction,
                embed=discord.Embed(
                    title="✅ 作成完了",
                    description="パネルを投稿しました",
                    color=0x57F287
                ),
                view=None,
            )

            bot.setup_state.pop(user_id, None)

        except Exception:
            print(traceback.format_exc())
            await _safe_ephemeral(interaction, "❌ 作成エラー")

        return

    # ----- selects -----

    elif cid == "setup:start_hour" and values:
        st["start_hour"] = values[0]

    elif cid == "setup:start_min" and values:
        st["start_min"] = values[0]

    elif cid == "setup:end_hour" and values:
        st["end_hour"] = values[0]

    elif cid == "setup:end_min" and values:
        st["end_min"] = values[0]

    elif cid == "setup:interval" and values:
        st["interval"] = int(values[0])

    elif cid == "setup:notify_channel" and values:
        st["notify_channel_id"] = str(values[0])

    # ----- 再描画 -----

    _recalc_hm(st)

    embed = build_setup_embed(st)
    view = build_setup_view(st)

    await _safe_edit(interaction, embed=embed, view=view)


# =============================
# entry
# =============================

async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):

    try:
        dm = getattr(bot, "dm", None)
        if dm is None:
            return

        # setup wizard
        cid = interaction.data.get("custom_id") if interaction.data else None

        if interaction.type == discord.InteractionType.modal_submit:
            await handle_setup(bot, interaction, dm)
            return

        if cid and cid.startswith("setup:"):
            await handle_setup(bot, interaction, dm)
            return

        # ここに panel系を後で追加

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())