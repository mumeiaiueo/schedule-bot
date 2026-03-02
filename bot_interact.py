import traceback
import discord

from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import build_hm, hm_to_minutes

async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            if not interaction.response.is_done():
                await interaction.response.send_message("状態がありません。/setup をやり直してね", ephemeral=True)
            return

        data = interaction.data or {}
        cid = data.get("custom_id") or ""
        values = data.get("values", [])

        # ===== buttons =====
        if cid.startswith("setup:day:"):
            st["day"] = cid.split(":")[-1]

        elif cid == "setup:step:2":
            st["step"] = 2

        elif cid == "setup:step:1":
            st["step"] = 1

        elif cid == "setup:everyone:toggle":
            st["everyone"] = not bool(st.get("everyone", False))

        elif cid == "setup:title:open":
            await interaction.response.send_modal(TitleModal(st))
            return

        elif cid == "setup:create":
            # まずACK（これを1回だけ）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            # start/end 組み立て
            start = build_hm(st.get("start_hh"), st.get("start_mm"))
            end   = build_hm(st.get("end_hh"), st.get("end_mm"))
            st["start"] = start
            st["end"] = end

            # バリデーション
            if not start or not end:
                await interaction.followup.send("開始/終了(時・分)を選んでね", ephemeral=True)
                return
            if not st.get("interval"):
                await interaction.followup.send("間隔を選んでね", ephemeral=True)
                return
            if hm_to_minutes(start) >= hm_to_minutes(end):
                await interaction.followup.send("終了は開始より後にしてね", ephemeral=True)
                return

            notify_ch = st.get("notify_channel") or interaction.channel_id

            # DB保存（panelsテーブルに合わせる）
            await bot.dm.create_panel_record(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                day_key=st.get("day", "today"),
                payload={
                    "start_hh": st["start_hh"],
                    "start_mm": st["start_mm"],
                    "end_hh": st["end_hh"],
                    "end_mm": st["end_mm"],
                    "interval_minutes": int(st["interval"]),
                    "title": st.get("title", "") or "",
                    "mention_everyone": bool(st.get("everyone", False)),
                    "notify_channel_id": notify_ch,
                }
            )

            await interaction.followup.send("✅ DBに保存したよ！", ephemeral=True)

            # ✅ ここは response じゃなく message.edit（ack済みなので）
            try:
                await interaction.message.edit(
                    embed=build_setup_embed(st),
                    view=build_setup_view(st)
                )
            except Exception:
                pass

            return

        # ===== selects =====
        if cid == "setup:start_hour" and values:
            st["start_hh"] = values[0]
        elif cid == "setup:start_min" and values:
            st["start_mm"] = values[0]
        elif cid == "setup:end_hour" and values:
            st["end_hh"] = values[0]
        elif cid == "setup:end_min" and values:
            st["end_mm"] = values[0]
        elif cid == "setup:interval" and values:
            st["interval"] = values[0]
        elif cid == "setup:notify_channel" and values:
            st["notify_channel"] = int(values[0])

        # start/end を表示用に組み立て
        st["start"] = build_hm(st.get("start_hh"), st.get("start_mm"))
        st["end"]   = build_hm(st.get("end_hh"), st.get("end_mm"))

        # ===== 画面更新 =====
        if not interaction.response.is_done():
            await interaction.response.edit_message(
                embed=build_setup_embed(st),
                view=build_setup_view(st)
            )
        else:
            await interaction.message.edit(
                embed=build_setup_embed(st),
                view=build_setup_view(st)
            )

    except Exception:
        print("❌ handle_component error")
        print(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("内部エラー。ログ見てね", ephemeral=True)
        except Exception:
            pass