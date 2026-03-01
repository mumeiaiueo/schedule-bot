import traceback
import discord
from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes

async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            await interaction.response.send_message("状態がありません。/setup をやり直してね", ephemeral=True)
            return

        cid = getattr(interaction.data, "get", lambda _k, _d=None: None)("custom_id")

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
            # バリデーション
            if not st.get("start") or not st.get("end"):
                await interaction.response.send_message("開始/終了を選んでね", ephemeral=True)
                return
            if not st.get("interval"):
                await interaction.response.send_message("間隔を選んでね", ephemeral=True)
                return

            # 時刻の整合（start < end）
            if hm_to_minutes(st["start"]) >= hm_to_minutes(st["end"]):
                await interaction.response.send_message("終了は開始より後にしてね", ephemeral=True)
                return

            # 通知チャンネル（未選択ならこのチャンネル）
            notify_ch = st.get("notify_channel") or interaction.channel_id

            # DB保存（最小）
            await interaction.response.defer(ephemeral=True)
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
        if interaction.type == discord.InteractionType.component:
            # discord.py は values を interaction.data["values"] に持ってる
            values = interaction.data.get("values", [])

            if cid == "setup:start":
                st["start"] = values[0]
            elif cid == "setup:end":
                st["end"] = values[0]
            elif cid == "setup:interval":
                st["interval"] = values[0]
            elif cid == "setup:notify_channel":
                # channel select: value は channel id(str)
                st["notify_channel"] = int(values[0])

        # 画面更新（元メッセージ編集）
        # ※ ここで response.defer 済み/未済み でも edit は followup で安全に行く
        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

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