# bot_interact.py
import traceback
from datetime import datetime, timedelta, timezone

import discord

from views.setup_wizard import build_setup_embed, build_setup_view


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _refresh_setup(interaction: discord.Interaction, st: dict):
    try:
        embed = build_setup_embed(st)
        view = build_setup_view(st)
        await interaction.message.edit(embed=embed, view=view)
    except Exception:
        pass


def _get_state(client: discord.Client, user_id: int) -> dict:
    if not hasattr(client, "setup_state"):
        client.setup_state = {}
    st = client.setup_state.get(user_id)
    if st is None:
        st = {
            "day": None,
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
        client.setup_state[user_id] = st
    return st


async def handle_interaction(client, interaction: discord.Interaction):
    try:
        # component以外（スラッシュ等）は discord.py に任せる
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not custom_id:
            return

        await safe_defer(interaction, ephemeral=True)

        # -----------------------------
        # 予約パネル（既存）
        # -----------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await client.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await client.dm.render_panel(client, panel_id)
            await safe_send(interaction, msg)
            return

        # -----------------------------
        # setupウィザード
        # -----------------------------
        if custom_id.startswith("setup:"):
            st = _get_state(client, interaction.user.id)

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

            elif custom_id == "setup:interval" and values:
                st["interval"] = int(values[0])

            elif custom_id == "setup:notify_channel" and values:
                # ChannelSelect は values に channel_id が入る
                st["notify_channel_id"] = str(values[0])

            elif custom_id == "setup:everyone:toggle":
                st["everyone"] = not st["everyone"]

            # start/end 文字列確定
            if st.get("start_hour") and st.get("start_min"):
                st["start"] = f"{st['start_hour']}:{st['start_min']}"
            if st.get("end_hour") and st.get("end_min"):
                st["end"] = f"{st['end_hour']}:{st['end_min']}"

            # 作成ボタン
            if custom_id == "setup:create":
                missing = []
                if not st.get("day"): missing.append("今日/明日")
                if not st.get("start"): missing.append("開始")
                if not st.get("end"): missing.append("終了")
                if not st.get("interval"): missing.append("間隔")
                if not st.get("notify_channel_id"): missing.append("通知チャンネル")

                if missing:
                    await safe_send(interaction, "❌ 未入力: " + " / ".join(missing))
                    await _refresh_setup(interaction, st)
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

                res = await client.dm.create_panel(
                    guild_id=str(interaction.guild_id),
                    channel_id=str(interaction.channel_id),
                    day_date=day,
                    title=st.get("title"),
                    start_at=start_at,
                    end_at=end_at,
                    interval_minutes=int(st["interval"]),
                    notify_channel_id=str(st["notify_channel_id"]),
                    created_by=str(interaction.user.id),
                )

                if not res.get("ok"):
                    await safe_send(interaction, "❌ 作成失敗（DB/権限/設定を確認）")
                    await _refresh_setup(interaction, st)
                    return

                await client.dm.render_panel(client, int(res["panel_id"]))
                # 状態破棄
                try:
                    client.setup_state.pop(interaction.user.id, None)
                except Exception:
                    pass

                await safe_send(interaction, "✅ 作成完了")
                return

            await _refresh_setup(interaction, st)
            await safe_send(interaction, "✅ 更新")
            return

        # その他
        await safe_send(interaction, f"unknown custom_id: {custom_id}")

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        await safe_send(interaction, f"❌ エラー: {repr(e)}")