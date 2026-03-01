# bot_interact.py
from __future__ import annotations

import traceback
from datetime import timedelta
import discord

from utils.time_utils import jst_now, build_range_jst
from views.setup_wizard import build_setup_embed, build_setup_view


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
        "wizard_message_id": None,
        "wizard_channel_id": None,
    }


def _ensure_setup_state(client: discord.Client, user_id: int) -> dict:
    if not hasattr(client, "setup_state") or client.setup_state is None:
        client.setup_state = {}
    st = client.setup_state.get(user_id)
    if not isinstance(st, dict):
        st = _default_setup_state()
        client.setup_state[user_id] = st
    for k, v in _default_setup_state().items():
        st.setdefault(k, v)
    if st.get("day") not in ("today", "tomorrow"):
        st["day"] = "today"
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


def _build_day_date(day_key: str):
    now = jst_now()
    return (now + timedelta(days=1)).date() if day_key == "tomorrow" else now.date()


async def _safe_ephemeral(interaction: discord.Interaction, text: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except Exception:
        pass


async def _edit_wizard_message(bot: discord.Client, st: dict, *, embed=None, view=None, content=None):
    try:
        ch = bot.get_channel(int(st["wizard_channel_id"])) if st.get("wizard_channel_id") else None
        mid = st.get("wizard_message_id")
        if not ch or not mid:
            return
        msg = await ch.fetch_message(int(mid))
        await msg.edit(content=content, embed=embed, view=view)
    except Exception:
        pass


class TitleModal(discord.ui.Modal, title="募集タイトル"):
    title_input = discord.ui.TextInput(
        label="タイトル（空欄OK）",
        required=False,
        max_length=50,
        placeholder="例：夜ランク募集 / 〇〇周回 など",
    )

    def __init__(self, bot: discord.Client, user_id: int):
        super().__init__()
        self.bot = bot
        self.user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        st = _ensure_setup_state(self.bot, self.user_id)
        st["title"] = str(self.title_input.value).strip() or None
        _recalc_hm(st)
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        await _edit_wizard_message(self.bot, st, embed=embed, view=view)
        await _safe_ephemeral(interaction, "✅ タイトルを設定しました")


async def handle_setup_wizard(bot: discord.Client, interaction: discord.Interaction, dm):
    st = _ensure_setup_state(bot, interaction.user.id)
    data = interaction.data or {}
    custom_id = data.get("custom_id")
    values = data.get("values") or []

    try:
        # -------- buttons
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
                st["step"] = 2

        elif custom_id == "setup:step:back":
            st["step"] = 1

        elif custom_id == "setup:title:open":
            # ✅ modalを開く（ここではACKしない）
            await interaction.response.send_modal(TitleModal(bot, interaction.user.id))
            return

        elif custom_id == "setup:create":
            _recalc_hm(st)

            if not st.get("start") or not st.get("end"):
                st["step"] = 1
                await _safe_ephemeral(interaction, "❌ 開始/終了の時刻を選んでください")
            elif not st.get("interval"):
                st["step"] = 2
                await _safe_ephemeral(interaction, "❌ 間隔（20/25/30）を選んでください")
            elif not st.get("notify_channel_id"):
                st["step"] = 2
                await _safe_ephemeral(interaction, "❌ 通知チャンネルを選んでください")
            else:
                try:
                    sh, sm = map(int, st["start"].split(":"))
                    eh, em = map(int, st["end"].split(":"))
                except Exception:
                    st["step"] = 1
                    await _safe_ephemeral(interaction, "❌ 時刻が不正です。選び直してね")
                else:
                    day_date = _build_day_date(st["day"])
                    start_at, end_at = build_range_jst(day_date, sh, sm, eh, em)

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
                        everyone=bool(st.get("everyone", False)),
                    )
                    if not res.get("ok"):
                        await _safe_ephemeral(interaction, f"❌ 作成失敗: {res.get('error', 'unknown')}")
                    else:
                        panel_id = int(res["panel_id"])
                        await dm.render_panel(bot, panel_id)

                        # ウィザードを完了表示にしてViewを外す
                        done = discord.Embed(title="✅ 作成しました", description="募集パネルを投稿しました。", color=0x57F287)
                        await _edit_wizard_message(bot, st, embed=done, view=None, content="✅ 完了")
                        await _safe_ephemeral(interaction, "✅ 完了！パネルを確認してね")

                        # state削除
                        try:
                            bot.setup_state.pop(interaction.user.id, None)
                        except Exception:
                            pass
                        return

        # -------- selects
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

        # 最後に再描画
        _recalc_hm(st)
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        await _edit_wizard_message(bot, st, embed=embed, view=view)

    except Exception:
        print("handle_setup_wizard error")
        print(traceback.format_exc())
        await _safe_ephemeral(interaction, "❌ ウィザード処理でエラー（ログ確認）")


async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    data = interaction.data or {}
    custom_id = data.get("custom_id") or ""
    if not custom_id.startswith("setup:"):
        return

    dm = getattr(bot, "dm", None)
    if dm is None:
        await _safe_ephemeral(interaction, "❌ DataManager未初期化")
        return

    await handle_setup_wizard(bot, interaction, dm)