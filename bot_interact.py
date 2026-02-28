# bot_interact.py
import traceback
import discord

async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # コンポーネント以外（スラッシュコマンド）は discord.py が処理するので何もしない
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        # まずACK（これが無いと「アプリケーションが応答しません」）
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        if not custom_id:
            return

        # 予約パネルのボタン
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
            await interaction.followup.send(msg, ephemeral=True)
            return

        # setupウィザードは「views側のcallback」が動く想定。
        # ここでは unknown を返すだけにして落ちないようにする。
        await interaction.followup.send(f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception:
        print("handle_interaction error")
        print(traceback.format_exc())
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ 内部エラー（ログ確認）", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 内部エラー（ログ確認）", ephemeral=True)
        except Exception:
            pass