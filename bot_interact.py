import traceback
import discord
from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes

async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            if not interaction.response.is_done():
                await interaction.response.send_message("状態がありません。/setup をやり直してね", ephemeral=True)
            return

        data = interaction.data or {}
        cid = data.get("custom_id") or ""

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
            # ✅ モーダルは defer してると出せないので、ここはそのまま送る
            if not interaction.response.is_done():
                await interaction.response.send_modal(TitleModal(st))
            return

        elif cid == "setup:create":
            # ✅ ここは重い処理なので defer（1回だけ）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            # バリデーション
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
            await interaction.followup.send("✅ 作成（DB保存）しました。次はパネル表示を追加していくよ", ephemeral=True)
            return

        # ===== selects =====
        values = data.get("values", [])

        if cid == "setup:start" and values:
            st["start"] = values[0]
        elif cid == "setup:end" and values:
            st["end"] = values[0]
        elif cid == "setup:interval" and values:
            st["interval"] = values[0]
        elif cid == "setup:notify_channel" and values:
            st["notify_channel"] = int(values[0])

        # ===== 画面更新 =====
        embed = build_setup_embed(st)
        view = build_setup_view(st)

        # ✅ response未使用なら edit_message が正解（これで「反応なし」減る）
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.message.edit(embed=embed, view=view)

    except Exception:
        print("❌ handle_component error")
        print(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("内部エラー。ログ見てね", ephemeral=True)
        except Exception:
            pass