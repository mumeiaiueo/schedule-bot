import traceback
import discord
from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal
from utils.time_utils import hm_to_minutes

def _rebuild_hm(st: dict, which: str):
    # which: "start" or "end"
    if which == "start":
        h = st.get("start_hour")
        m = st.get("start_min")
        if h is not None and m is not None:
            st["start"] = f"{int(h):02d}:{int(m):02d}"
    else:
        h = st.get("end_hour")
        m = st.get("end_min")
        if h is not None and m is not None:
            st["end"] = f"{int(h):02d}:{int(m):02d}"

async def handle_component(bot, interaction: discord.Interaction):
    try:
        st = bot.wizard_state.get(interaction.user.id)
        if not st:
            if not interaction.response.is_done():
                await interaction.response.send_message("状態がありません。/setup をやり直してね", ephemeral=True)
            return

        data = interaction.data or {}
        cid = data.get("custom_id") or ""

        # --- Modal submit（タイトル入力） ---
        if interaction.type == discord.InteractionType.modal_submit:
            # TitleModal.on_submit が st["title"] を更新する想定
            # ここでは画面更新だけ
            await interaction.response.send_message("✅ 反映しました", ephemeral=True)
            return

        # --- Buttons ---
        if cid.startswith("setup:day:"):
            st["day"] = cid.split(":")[-1]

        elif cid == "setup:step:2":
            st["step"] = 2

        elif cid == "setup:step:1":
            st["step"] = 1

        elif cid == "setup:everyone:toggle":
            st["everyone"] = not bool(st.get("everyone", False))

        elif cid == "setup:title:open":
            # ✅ モーダルは defer してると出せないので、ここは即 send_modal
            await interaction.response.send_modal(TitleModal(st))
            return

        elif cid == "setup:create":
            # ✅ ここだけ defer → followup（重い処理）
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

            # DB保存
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

            await interaction.followup.send("✅ 作成できた！DBに保存したよ", ephemeral=True)

            # defer済みなので response.edit_message は使わず、元メッセージを直接編集
            await interaction.message.edit(embed=build_setup_embed(st), view=build_setup_view(st))
            return

        # --- Selects ---
        values = data.get("values", [])
        if values:
            v = values[0]
            if cid == "setup:start_hour":
                st["start_hour"] = v
                _rebuild_hm(st, "start")
            elif cid == "setup:start_min":
                st["start_min"] = v
                _rebuild_hm(st, "start")
            elif cid == "setup:end_hour":
                st["end_hour"] = v
                _rebuild_hm(st, "end")
            elif cid == "setup:end_min":
                st["end_min"] = v
                _rebuild_hm(st, "end")
            elif cid == "setup:interval":
                st["interval"] = v
            elif cid == "setup:notify_channel":
                st["notify_channel"] = int(v)

        # --- 画面更新（通常はこれだけ） ---
        await interaction.response.edit_message(
            embed=build_setup_embed(st),
            view=build_setup_view(st),
        )

    except Exception:
        print("❌ handle_component error")
        print(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("内部エラー。ログ見てね", ephemeral=True)
        except Exception:
            pass