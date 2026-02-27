# bot_interact.py
import asyncio
import traceback
from datetime import datetime, timedelta, timezone

import discord

from views.setup_wizard import build_setup_embed, build_setup_view


JST = timezone(timedelta(hours=9))


async def _safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def _safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _edit_wizard(interaction: discord.Interaction, *, embed: discord.Embed, view: discord.ui.View):
    """
    ✅ ここが肝：
    - ephemeralは message.edit できないことがある
    - edit_original_response を使うと確実に更新できる
    """
    try:
        # interaction.message がある（通常メッセージ）ならそれを更新
        if getattr(interaction, "message", None) is not None:
            await interaction.message.edit(embed=embed, view=view)
            return
    except Exception:
        pass

    # ephemeral はこちら
    try:
        await interaction.edit_original_response(embed=embed, view=view)
    except Exception:
        pass


async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # 1) スラッシュ等は tree に渡す（sync済みならここが正道）
        if interaction.type == discord.InteractionType.application_command:
            try:
                res = bot.tree._from_interaction(interaction)
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
            return

        # 2) component だけ処理
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not isinstance(custom_id, str):
            return

        # ✅ 3秒対策：先にdefer
        await _safe_defer(interaction, ephemeral=True)

        # --------------------------
        # パネル予約（既存）
        # --------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            if len(parts) != 4:
                await _safe_send(interaction, "❌ ボタン形式が不正です")
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await bot.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await bot.dm.render_panel(bot, panel_id)
            await _safe_send(interaction, msg, ephemeral=True)
            return

        # --------------------------
        # setupウィザード（今回の本命）
        # --------------------------
        if custom_id.startswith("setup:"):
            st = bot.get_setup_state(interaction.user.id)

            if custom_id == "setup:day:today":
                st["day"] = "today"
            elif custom_id == "setup:day:tomorrow":
                st["day"] = "tomorrow"

            elif custom_id == "setup:start_hour" and values:
                st["start_hour"] = str(values[0])
            elif custom_id == "setup:start_min" and values:
                st["start_min"] = str(values[0])
            elif custom_id == "setup:end_hour" and values:
                st["end_hour"] = str(values[0])
            elif custom_id == "setup:end_min" and values:
                st["end_min"] = str(values[0])

            elif custom_id.startswith("setup:interval:"):
                st["interval"] = int(custom_id.split(":")[-1])

            elif custom_id == "setup:notify_channel" and values:
                st["notify_channel_id"] = str(values[0])

            elif custom_id == "setup:everyone:toggle":
                st["everyone"] = not bool(st.get("everyone"))

            elif custom_id == "setup:title:clear":
                st["title"] = None

            elif custom_id == "setup:create":
                # 必須チェック
                missing = []
                if not st.get("day"): missing.append("今日/明日")
                if not (st.get("start_hour") and st.get("start_min")): missing.append("開始時刻")
                if not (st.get("end_hour") and st.get("end_min")): missing.append("終了時刻")
                if not st.get("interval"): missing.append("間隔(20/25/30)")
                if not st.get("notify_channel_id"): missing.append("通知チャンネル")

                if missing:
                    await _safe_send(interaction, "❌ 未入力: " + " / ".join(missing), ephemeral=True)
                    embed = build_setup_embed(st)
                    view = build_setup_view(st)
                    await _edit_wizard(interaction, embed=embed, view=view)
                    return

                # 日付決定
                today = datetime.now(JST).date()
                day = today if st["day"] == "today" else (today + timedelta(days=1))

                sh = int(st["start_hour"]); sm = int(st["start_min"])
                eh = int(st["end_hour"]); em = int(st["end_min"])

                start_at = datetime(day.year, day.month, day.day, sh, sm, tzinfo=JST)
                end_at = datetime(day.year, day.month, day.day, eh, em, tzinfo=JST)
                if end_at <= start_at:
                    end_at += timedelta(days=1)

                # everyone付けたいならタイトルに埋め込む（通知処理側で使う想定）
                title = st.get("title")
                if st.get("everyone"):
                    if title:
                        title = f"@everyone {title}"
                    else:
                        title = "@everyone"

                res = await bot.dm.create_panel(
                    guild_id=str(interaction.guild_id),
                    channel_id=str(interaction.channel_id),
                    day_date=day,
                    title=title,
                    start_at=start_at,
                    end_at=end_at,
                    interval_minutes=int(st["interval"]),
                    notify_channel_id=str(st["notify_channel_id"]),
                    created_by=str(interaction.user.id),
                )

                if not res.get("ok"):
                    await _safe_send(interaction, f"❌ 作成失敗: {res.get('error','unknown')}", ephemeral=True)
                    embed = build_setup_embed(st)
                    view = build_setup_view(st)
                    await _edit_wizard(interaction, embed=embed, view=view)
                    return

                await bot.dm.render_panel(bot, int(res["panel_id"]))
                bot.clear_setup_state(interaction.user.id)

                # ✅ ウィザードは完了表示に更新（ephemeralでも確実に編集）
                done_embed = discord.Embed(title="✅ 作成完了", description="パネルを作成しました！", color=0x2ECC71)
                await _edit_wizard(interaction, embed=done_embed, view=discord.ui.View())
                return

            # 通常の更新
            embed = build_setup_embed(st)
            view = build_setup_view(st)
            await _edit_wizard(interaction, embed=embed, view=view)
            return

        # 想定外
        await _safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        await _safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)