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

    # 重要キーが欠けてても復元（「古いウィザード」連打を止める）
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
    # component は bot_app.py 側で defer() 済みの可能性が高いので followup を優先
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _safe_edit_message(interaction: discord.Interaction, *, embed=None, view=None, content=None):
    # ephemeral message でも interaction.message.edit が基本いける
    try:
        if interaction.message:
            await interaction.message.edit(content=content, embed=embed, view=view)
            return
    except Exception:
        pass

    # fallback
    try:
        await interaction.edit_original_response(content=content, embed=embed, view=view)
    except Exception:
        pass


# -----------------------------
# Setup Wizard Handler
# -----------------------------
async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    user_id = interaction.user.id
    st = _ensure_setup_state(bot, user_id)

    data = interaction.data or {}
    custom_id = data.get("custom_id")

    # セレクトは values に入る
    values = data.get("values") or []

    # ---- buttons: setup:day:today / tomorrow
    if custom_id == "setup:day:today":
        st["day"] = "today"
    elif custom_id == "setup:day:tomorrow":
        st["day"] = "tomorrow"
    elif custom_id == "setup:everyone:toggle":
        st["everyone"] = not bool(st.get("everyone"))

    # ---- step control
    elif custom_id == "setup:step:next":
        # step1 validation
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
                # start < end をチェック（同日内想定）
                if (eh[0], eh[1]) <= (sh[0], sh[1]):
                    await _safe_ephemeral(interaction, "❌ 終了は開始より後にしてください（同じ/前は不可）")
                else:
                    st["step"] = 2

    elif custom_id == "setup:step:back":
        st["step"] = 1

    # ---- create
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
            # notify_channel 未設定なら「このチャンネル」を使う（未設定で止まらないように）
            notify_channel_id = st.get("notify_channel_id") or str(interaction.channel_id)

            # JSTで start/end datetime を作る
            day_date = _build_day_date(st["day"])
            sh = _parse_hm(st["start"])
            eh = _parse_hm(st["end"])
            if not sh or not eh:
                await _safe_ephemeral(interaction, "❌ 時刻が不正です。Step1で選び直してね")
                st["step"] = 1
            else:
                start_at = datetime(day_date.year, day_date.month, day_date.day, sh[0], sh[1], tzinfo=jst_now().tzinfo)
                end_at = datetime(day_date.year, day_date.month, day_date.day, eh[0], eh[1], tzinfo=jst_now().tzinfo)

                # create_panel → render_panel
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

                        # ウィザードを完了表示（view外す）
                        embed = discord.Embed(title="✅ 作成しました", description="パネルを投稿しました。", color=0x57F287)
                        await _safe_edit_message(interaction, embed=embed, view=None)
                        await _safe_ephemeral(interaction, "✅ 完了！パネルを確認してね")

                        # 状態クリア（連続作成したいなら消してOK）
                        try:
                            bot.setup_state.pop(interaction.user.id, None)
                        except Exception:
                            pass

                        return  # 完了なのでここで終了

                except Exception:
                    await _safe_ephemeral(interaction, "❌ 作成中にエラー（ログ確認）")
                    print("setup:create error")
                    print(traceback.format_exc())

    # ---- selects
    # hour/min selects
    elif custom_id == "setup:start_hour" and values:
        st["start_hour"] = values[0]
    elif custom_id == "setup:start_min" and values:
        st["start_min"] = values[0]
    elif custom_id == "setup:end_hour" and values:
        st["end_hour"] = values[0]
    elif custom_id == "setup:end_min" and values:
        st["end_min"] = values[0]

    # interval select
    elif custom_id == "setup:interval" and values:
        try:
            st["interval"] = int(values[0])
        except Exception:
            st["interval"] = None

    # notify channel select
    elif custom_id == "setup:notify_channel" and values:
        st["notify_channel_id"] = str(values[0])

    # ここまで来たら embed/view を更新
    _recalc_hm(st)
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    await _safe_edit_message(interaction, embed=embed, view=view)


# -----------------------------
# Generic component handler (buttons on panel etc.)
# -----------------------------
async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    """
    bot_app.py から呼ばれる入口。
    - setup wizard: custom_id startswith "setup:"
    - それ以外は必要に応じて増やせる
    """
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        if not custom_id:
            return

        dm = getattr(bot, "dm", None)

        # ✅ setup wizard
        if custom_id.startswith("setup:") or custom_id.startswith("setup"):
            if dm is None:
                await _safe_ephemeral(interaction, "❌ DataManager未初期化")
                return
            await handle_setup_wizard(bot, interaction, dm)
            return

        # ここから先は「あなたのPanelViewのcustom_id仕様」に合わせて増やせる
        # 例： slot:123 みたいな仕様なら予約トグルを実装できる
        # （今はウィザード修正が目的なので、未定義は黙って無視）
        return

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            await _safe_ephemeral(interaction, "❌ ボタン処理でエラー（ログ確認）")
        except Exception:
            pass