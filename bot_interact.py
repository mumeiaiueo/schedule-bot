from __future__ import annotations

import traceback
from datetime import datetime, timedelta

import discord

from utils.time_utils import jst_now, jst_today_date, build_range_jst
from views.setup_wizard import build_setup_embed, build_setup_view, TitleModal


def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",            # "today" | "tomorrow"
        "start": None,             # "HH:MM"
        "end": None,               # "HH:MM"
        "interval": None,          # int minutes
        "notify_channel_id": None, # str
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
    if st.get("day") not in ("today", "tomorrow"):
        st["day"] = "today"

    return st


def _day_date(day_key: str):
    return jst_today_date(1 if day_key == "tomorrow" else 0)


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


def _parse_panel_slot(custom_id: str):
    # panel:slot:{panel_id}:{slot_id}
    if not custom_id.startswith("panel:slot:"):
        return None
    p = custom_id.split(":")
    if len(p) != 4:
        return None
    try:
        return int(p[2]), int(p[3])
    except Exception:
        return None


def _parse_panel_notifytoggle(custom_id: str):
    # panel:notifytoggle:{panel_id}
    if not custom_id.startswith("panel:notifytoggle:"):
        return None
    p = custom_id.split(":")
    if len(p) != 3:
        return None
    try:
        return int(p[2])
    except Exception:
        return None


def _parse_panel_breaktoggle(custom_id: str):
    # panel:breaktoggle:{panel_id}
    if not custom_id.startswith("panel:breaktoggle:"):
        return None
    p = custom_id.split(":")
    if len(p) != 3:
        return None
    try:
        return int(p[2])
    except Exception:
        return None


def _parse_panel_breakselect(custom_id: str):
    # panel:breakselect:{panel_id}
    if not custom_id.startswith("panel:breakselect:"):
        return None
    p = custom_id.split(":")
    if len(p) != 3:
        return None
    try:
        return int(p[2])
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

    # day
    if custom_id == "setup:day:today":
        st["day"] = "today"
    elif custom_id == "setup:day:tomorrow":
        st["day"] = "tomorrow"

    # time select
    elif custom_id == "setup:start" and values:
        st["start"] = values[0]
    elif custom_id == "setup:end" and values:
        st["end"] = values[0]
    elif custom_id == "setup:interval" and values:
        try:
            st["interval"] = int(values[0])
        except Exception:
            st["interval"] = None
    elif custom_id == "setup:notify_channel" and values:
        st["notify_channel_id"] = str(values[0])

    # toggles
    elif custom_id == "setup:everyone:toggle":
        st["everyone"] = not bool(st.get("everyone"))

    # title modal open
    elif custom_id == "setup:title:open":
        try:
            await interaction.response.send_modal(TitleModal())
            return
        except Exception:
            await _safe_ephemeral(interaction, "❌ タイトル入力を開けませんでした")
            return

    # modal submit (タイトル)
    if interaction.type == discord.InteractionType.modal_submit:
        try:
            # custom_id は modal 側
            if data.get("custom_id") == "setup:title:modal":
                title_val = (data.get("components") or [])[0]["components"][0].get("value")
                st["title"] = (title_val or "").strip() or None
        except Exception:
            pass

    # next/back
    if custom_id == "setup:step:next":
        if not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了を選んでください")
        else:
            st["step"] = 2

    elif custom_id == "setup:step:back":
        st["step"] = 1

    # create
    elif custom_id == "setup:create":
        if not st.get("start") or not st.get("end"):
            await _safe_ephemeral(interaction, "❌ 開始/終了を選んでください")
            st["step"] = 1
        elif not st.get("interval"):
            await _safe_ephemeral(interaction, "❌ 間隔（分）を選んでください")
            st["step"] = 2
        else:
            day_date = _day_date(st["day"])
            sh, sm = map(int, st["start"].split(":"))
            eh, em = map(int, st["end"].split(":"))

            start_at, end_at = build_range_jst(day_date, sh, sm, eh, em)

            notify_channel_id = st.get("notify_channel_id") or str(interaction.channel_id)

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
                    everyone=bool(st.get("everyone")),
                )
                if not res.get("ok"):
                    await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error','unknown')}")
                else:
                    panel_id = int(res["panel_id"])
                    await dm.render_panel(bot, panel_id)

                    # @everyone は作成時に1回だけ
                    if st.get("everyone"):
                        ch = bot.get_channel(int(interaction.channel_id))
                        if ch:
                            try:
                                await ch.send("@everyone 募集パネルを作成しました")
                            except Exception:
                                pass

                    embed = discord.Embed(title="✅ 作成しました", description="パネルを投稿しました。", color=0x57F287)
                    await _safe_edit_message(interaction, embed=embed, view=None)
                    await _safe_ephemeral(interaction, "✅ 完了！パネルを確認してね")

                    bot.setup_state.pop(interaction.user.id, None)
                    return
            except Exception:
                print("setup:create error")
                print(traceback.format_exc())
                await _safe_ephemeral(interaction, "❌ 作成中にエラー（ログ確認）")

    # redraw wizard message
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    await _safe_edit_message(interaction, embed=embed, view=view)


# -----------------------------
# Panel handlers
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
        print(traceback.format_exc())


async def handle_notify_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return
    ok, msg = await dm.toggle_notify_paused(panel_id)
    await _safe_ephemeral(interaction, ("✅ " if ok else "❌ ") + msg)
    await dm.render_panel(bot, panel_id)


async def handle_break_toggle(bot: discord.Client, interaction: discord.Interaction, dm, panel_id: int):
    if not await dm.is_manager(interaction):
        await _safe_ephemeral(interaction, "❌ 管理者/管理ロールのみ操作できます")
        return
    try:
        view = await dm.build_break_select_view(panel_id)
        await interaction.followup.send("🛠 休憩にする/解除する枠を選んでください", view=view, ephemeral=True)
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
    await dm.render_panel(bot, panel_id)


# -----------------------------
# Entry point
# -----------------------------
async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        if not custom_id:
            return

        dm = getattr(bot, "dm", None)
        if dm is None:
            await _safe_ephemeral(interaction, "❌ DataManager未初期化")
            return

        # setup wizard
        if custom_id.startswith("setup:") or interaction.type == discord.InteractionType.modal_submit:
            await handle_setup_wizard(bot, interaction, dm)
            return

        # slot
        ps = _parse_panel_slot(custom_id)
        if ps:
            panel_id, slot_id = ps
            await handle_panel_slot(bot, interaction, dm, panel_id, slot_id)
            return

        # notify toggle
        pid = _parse_panel_notifytoggle(custom_id)
        if pid is not None:
            await handle_notify_toggle(bot, interaction, dm, pid)
            return

        # break toggle
        pid = _parse_panel_breaktoggle(custom_id)
        if pid is not None:
            await handle_break_toggle(bot, interaction, dm, pid)
            return

        # break select
        pid = _parse_panel_breakselect(custom_id)
        if pid is not None:
            values = (data.get("values") or [])
            if not values:
                return
            try:
                slot_id = int(values[0])
            except Exception:
                await _safe_ephemeral(interaction, "❌ 選択値が不正です")
                return
            await handle_break_select(bot, interaction, dm, pid, slot_id)
            return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")