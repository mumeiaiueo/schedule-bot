import traceback
import discord

from views.setup_wizard import build_setup_view, build_setup_embed, TitleModal


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
        cid = data.get("custom_id")
        values = data.get("values", [])

        # ===== ボタン処理 =====
        if cid and cid.startswith("setup:day:"):
            st["day"] = cid.split(":")[-1]

        elif cid == "setup:step:2":
            st["step"] = 2

        elif cid == "setup:step:1":
            st["step"] = 1

        elif cid == "setup:everyone:toggle":
            st["everyone"] = not st.get("everyone", False)

        elif cid == "setup:title:open":
            await interaction.response.send_modal(TitleModal(st))
            return

        elif cid == "setup:create":
            # まずACK
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            try:
                await interaction.followup.send(
                    "✅ 作成ボタンは正常に反応しています",
                    ephemeral=True
                )
            except Exception:
                print("create followup error")
                print(traceback.format_exc())

            return

        # ===== セレクト処理 =====
        if cid == "setup:interval" and values:
            st["interval"] = values[0]

        elif cid == "setup:notify_channel" and values:
            st["notify_channel"] = int(values[0])

        # UI更新
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