# bot_interact.py
import traceback
import discord
from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes


def _rebuild_time(st: dict):
    """start_hour/start_min → start を作る"""
    sh = st.get("start_hour")
    sm = st.get("start_min")
    eh = st.get("end_hour")
    em = st.get("end_min")

    if sh is not None and sm is not None:
        st["start"] = f"{int(sh):02d}:{int(sm):02d}"

    if eh is not None and em is not None:
        st["end"] = f"{int(eh):02d}:{int(em):02d}"


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
        cid = data.get("custom_id") or ""
        values = data.get("values", [])

        # ===== ボタン処理 =====

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
            # 重い処理なので defer
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
                guild_id=int(interaction.guild_id),
                channel_id=int(interaction.channel_id),
                day_key=st["day"],
                payload={
                    "start": st["start"],
                    "end": st["end"],
                    "interval": int(st["interval"]),
                    "title": st.get("title", ""),
                    "everyone": bool(st.get("everyone", False)),
                    "notify_channel": int(notify_ch),
                }
            )

            await interaction.followup.send("✅ 作成しました", ephemeral=True)

            # メッセージ更新
            await interaction.message.edit(
                embed=build_setup_embed(st),
                view=build_setup_view(st)
            )
            return

        # ===== セレクト処理 =====

        if values:
            value = values[0]

            if cid == "setup:start_hour":
                st["start_hour"] = value

            elif cid == "setup:start_min":
                st["start_min"] = value

            elif cid == "setup:end_hour":
                st["end_hour"] = value

            elif cid == "setup:end_min":
                st["end_min"] = value

            elif cid == "setup:interval":
                st["interval"] = value

            elif cid == "setup:notify_channel":
                st["notify_channel"] = int(value)

            # 時刻組み立て
            _rebuild_time(st)

        # ===== 通常更新 =====

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
                await interaction.response.send_message(
                    "内部エラー。ログ見てね",
                    ephemeral=True
                )
        except Exception:
            pass