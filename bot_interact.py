# bot_interact.py（setup部分：完全版）
from __future__ import annotations

import traceback
from datetime import datetime, timedelta

import discord

from utils.time_utils import jst_now
from views.setup_wizard import build_setup_embed, build_setup_view, TitleModal


def _default_setup_state() -> dict:
    return {
        "step": 1,
        "day": "today",            # ✅ デフォルト今日
        "start_hour": None,
        "start_min": None,
        "end_hour": None,
        "end_min": None,
        "start": None,
        "end": None,
        "interval": None,
        "notify_channel_id": None, # ✅ 必須
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


async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_edit_message(interaction: discord.Interaction, *, embed=None, view=None, content=None):
    # component interactionでは message.edit / response.edit_message が安定
    try:
        if not interaction.response.is_done():
            await interaction.response.edit_message(content=content, embed=embed, view=view)
            return
    except Exception:
        pass
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


def _extract_modal_text(interaction: discord.Interaction) -> str:
    # modal_submit の入力値を取り出す
    try:
        data = interaction.data or {}
        comps = data.get("components") or []
        # [{type:1, components:[{type:4,value:"..."}]}] の形が多い
        for row in comps:
            for c in (row.get("components") or []):
                if "value" in c:
                    return str(c.get("value") or "").strip()
    except Exception:
        pass
    return ""


# -----------------------------
# Setup Wizard Handler（完成版）
# -----------------------------
async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    user_id = interaction.user.id
    st = _ensure_setup_state(bot, user_id)

    # modal submit（タイトル入力）
    if interaction.type == discord.InteractionType.modal_submit:
        data = interaction.data or {}
        cid = data.get("custom_id") or ""
        if cid == "setup:titlemodal":
            title = _extract_modal_text(interaction)
            st["title"] = title if title else None
            # ここではephemeralでOK（元のウィザード表示は次の操作で更新される）
            await _safe_ephemeral(interaction, f"✅ タイトルを設定しました：{st['title'] or '（未設定）'}")
        return

    # component
    data = interaction.data or {}
    custom_id = data.get("custom_id") or ""
    values = data.get("values") or []

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
                await _safe_ephemeral(interaction, "❌ 時刻の形式が不正です")
            else:
                if (eh[0], eh[1]) <= (sh[0], sh[1]):
                    await _safe_ephemeral(interaction, "❌ 終了は開始より後にしてください")
                else:
                    st["step"] = 2

    elif custom_id == "setup:step:back":
        st["step"] = 1

    elif custom_id == "setup:title:open":
        # ✅ ここはACK前にモーダルを出す必要がある
        try:
            if not interaction.response.is_done():
                await interaction.response.send_modal(TitleModal(current=st.get("title")))
        except Exception:
            await _safe_ephemeral(interaction, "❌ タイトル入力を開けませんでした")
        return

    elif custom_id == "setup:create":
        _recalc_hm(st)

        if not st.get("start") or not st.get("end"):
            st["step"] = 1
            await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
        elif not st.get("interval"):
            st["step"] = 2
            await _safe_ephemeral(interaction, "❌ 間隔（分）を選んでください")
        elif not st.get("notify_channel_id"):
            st["step"] = 2
            await _safe_ephemeral(interaction, "❌ 通知チャンネルは必須です（Step2で選択してください）")
        else:
            day_date = _build_day_date(st["day"])
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                st["step"] = 1
                await _safe_ephemeral(interaction, "❌ 時刻が不正です。Step1で選び直してね")
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
                        notify_channel_id=str(st["notify_channel_id"]),
                        created_by=str(interaction.user.id),
                        # everyoneはDataManager側で投稿に反映させる（後で実装）
                        # everyone=bool(st.get("everyone", False)),
                    )

                    if not res.get("ok"):
                        await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error', 'unknown')}")
                    else:
                        panel_id = int(res["panel_id"])
                        await dm.render_panel(bot, panel_id)

                        await _safe_edit_message(
                            interaction,
                            embed=discord.Embed(title="✅ 作成しました", description="パネルを投稿しました。", color=0x57F287),
                            view=None,
                        )
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
# Entry point（ここは今のあなたの既存パネル処理に繋げる）
# -----------------------------
async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    try:
        dm = getattr(bot, "dm", None)
        if dm is None:
            await _safe_ephemeral(interaction, "❌ DataManager未初期化")
            return

        # setup wizard（component / modal）
        data = interaction.data or {}
        cid = data.get("custom_id") or ""
        if interaction.type == discord.InteractionType.modal_submit:
            if cid.startswith("setup:"):
                await handle_setup_wizard(bot, interaction, dm)
            return

        if cid.startswith("setup:"):
            await handle_setup_wizard(bot, interaction, dm)
            return

        # ※ここから下はあなたの panel / notify / break の既存処理を入れる場所
        # （次のステップで上から順に整備する）

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass