import traceback
import discord
from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes


async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "状態がありません。/setup をやり直してね",
                    ephemeral=True
                )
            return

        data = interaction.data or {}
        cid = data.get("custom_id", "")
        values = data.get("values", [])

        # ===== ボタン =====

        if cid.startswith("setup:day:"):
            st["day"] = cid.split(":")[-1]

        elif cid == "setup:step:2":
            st["step"] = 2

        elif cid == "setup:step:1":
            st["step"] = 1

        elif cid == "setup:everyone:toggle":
            st["everyone"] = not bool(st.get("everyone", False))

        elif cid == "setup:title:open":
            if not interaction.response.is_done():
                await interaction.response.send_modal(TitleModal(st))
            return

        elif cid == "setup:create":
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            if not st.get("start") or not st.get("end"):
                await interaction.followup.send("開始/終了を選んでね", ephemeral=True)
                return

            if not st.get("interval"):
                await interaction.followup.send("間隔を選んでね", ephemeral=True)
                return

            if hm_to_minutes(st["start"]) >= hm_to_minutes(st["end"]):
                await interaction.followup.send("終了は開始より後にしてね", ephemeral=True)
                return

            notify_ch = st.get("notify_channel") or interaction.channel_id

            await bot.dm.create_panel_record(
                guild_id=interaction.guild_id,
                channel_id=interaction.channel_id,
                day_key=st["day"],
                payload={
                    "start": st["start"],
                    "end": st["end"],
                    "interval": int(st["interval"]),
                    "title": st.get("title", ""),
                    "everyone": bool(st.get("everyone", False)),
                    "notify_channel": notify_ch,
                }
            )

            await interaction.followup.send("✅ 作成しました", ephemeral=True)
            return

        # ===== セレクト =====

        if cid == "setup:start_hour" and values:
            st["start_hour"] = values[0]

        elif cid == "setup:start_min" and values:
            st["start_min"] = values[0]

        elif cid == "setup:end_hour" and values:
            st["end_hour"] = values[0]

        elif cid == "setup:end_min" and values:
            st["end_min"] = values[0]

        elif cid == "setup:interval" and values:
            st["interval"] = values[0]

        elif cid == "setup:notify_channel" and values:
            st["notify_channel"] = int(values[0])

        # HH:MM 組み立て
        if st.get("start_hour") and st.get("start_min"):
            st["start"] = f'{st["start_hour"]}:{st["start_min"]}'

        if st.get("end_hour") and st.get("end_min"):
            st["end"] = f'{st["end_hour"]}:{st["end_min"]}'

        # ===== 画面更新 =====

        embed = build_setup_embed(st)
        view = build_setup_view(st)

        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.followup.edit_message(
                message_id=interaction.message.id,
                embed=embed,
                view=view
            )

    except Exception:
        print("❌ handle_component error")
        print(traceback.format_exc())