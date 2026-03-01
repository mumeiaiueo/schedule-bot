# bot_interact.py
import traceback
import discord


async def handle_component_or_modal(bot, interaction: discord.Interaction):
    """
    ボタン/セレクト/モーダルをここで受けて、custom_id を見て views に流す。
    ※ views 側は bot.dm を使ってDB更新→パネル更新、の責務
    """
    try:
        cid = None
        if interaction.data and isinstance(interaction.data, dict):
            cid = interaction.data.get("custom_id")

        if not cid:
            return

        # ここで custom_id の prefix で views に振り分け
        # 例: setup:..., panel:..., time:... など
        if cid.startswith("setup:"):
            from views.setup_wizard import handle_setup_interaction
            await handle_setup_interaction(bot, interaction, cid)
            return

        if cid.startswith("panel:"):
            from views.panel_view import handle_panel_interaction
            await handle_panel_interaction(bot, interaction, cid)
            return

        if cid.startswith("time:"):
            from views.time_picker_view import handle_timepicker_interaction
            await handle_timepicker_interaction(bot, interaction, cid)
            return

        # 未対応
        return

    except Exception:
        print("handle_component_or_modal error")
        print(traceback.format_exc())
        # 既にdefer済み前提なので followup でOK
        try:
            await interaction.followup.send("❌ 内部エラー（ログ確認）", ephemeral=True)
        except Exception:
            pass