# bot_interact.py
import traceback
from datetime import datetime, timedelta, timezone
import discord


async def _safe_defer(interaction: discord.Interaction, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def _safe_send(interaction: discord.Interaction, content: str, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _refresh_setup(bot, interaction: discord.Interaction):
    # views側の関数を使う（あなたの既存）
    from views.setup_wizard import build_setup_embed, build_setup_view

    st = bot.setup_state.get(interaction.user.id)
    if not st:
        return
    embed = build_setup_embed(st)
    view = build_setup_view(st)
    try:
        await interaction.message.edit(embed=embed, view=view)
    except Exception:
        pass


async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # ---------- スラッシュコマンド等（component以外）は tree に渡す ----------
        if interaction.type != discord.InteractionType.component:
            try:
                # discord.pyのバージョン差を吸収（内部API）
                if hasattr(bot.tree, "_call"):
                    await bot.tree._call(interaction)
                else:
                    res = bot.tree._from_interaction(interaction)
                    if hasattr(res, "__await__"):
                        await res
            except Exception:
                print("tree dispatch error")
                print(traceback.format_exc())
            return

        # ---------- component（ボタン/セレクト） ----------
        await _safe_defer(interaction, ephemeral=True)

        data = interaction.data or {}
        custom_id = (data.get("custom_id") or "")
        values = data.get("values") or []

        # setup_state を必ず用意
        if not hasattr(bot, "setup_state") or bot.setup_state is None:
            bot.setup_state = {}

        # -----------------------------
        # 予約ボタン（既存）
        # -----------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
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

        # -----------------------------
        # setup ウィザード
        # -----------------------------
        if custom_id.startswith("setup:"):
            st = bot.setup_state.get(interaction.user.id)
            if st is None:
                # setup_channel押してない場合などの保険
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
                bot.setup_state[interaction.user.id] = st

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

            elif custom_id.startswith("setup:interval:"):
                st["interval"] = int(custom_id.split(":")[-1])

            elif custom_id == "setup:notify_channel" and values:
                st["notify_channel_id"] = str(values[0])

            elif custom_id == "setup:everyone:toggle":
                st["everyone"] = not st["everyone"]

            # 時刻確定（UIの表示用）
            if st.get("start_hour") and st.get("start_min"):
                st["start"] = f"{st['start_hour']}:{st['start_min']}"
            if st.get("end_hour") and st.get("end_min"):
                st["end"] = f"{st['end_hour']}:{st['end_min']}"

            # 作成ボタン
            if custom_id == "setup:create":
                missing = []
                if not st.get("day"):
                    missing.append("今日/明日")
                if not st.get("start"):
                    missing.append("開始")
                if not st.get("end"):
                    missing.append("終了")
                if not st.get("interval"):
                    missing.append("間隔")
                if not st.get("notify_channel_id"):
                    missing.append("通知チャンネル")

                if missing:
                    await _safe_send(interaction, "❌ 未入力: " + " / ".join(missing), ephemeral=True)
                    await _refresh_setup(bot, interaction)
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

                res = await bot.dm.create_panel(
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
                    await _safe_send(interaction, "❌ 作成失敗", ephemeral=True)
                    await _refresh_setup(bot, interaction)
                    return

                await bot.dm.render_panel(bot, int(res["panel_id"]))
                bot.setup_state.pop(interaction.user.id, None)
                await _safe_send(interaction, "✅ 作成完了", ephemeral=True)
                return

            await _refresh_setup(bot, interaction)
            await _safe_send(interaction, "✅ 更新", ephemeral=True)
            return

        await _safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        await _safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)


# ✅ 互換エイリアス（どっちでimportされても動く）
async def handle_component_interaction(bot, interaction: discord.Interaction):
    return await handle_interaction(bot, interaction)