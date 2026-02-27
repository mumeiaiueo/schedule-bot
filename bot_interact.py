# bot_interact.py
import asyncio
import traceback
import discord


async def safe_defer(interaction: discord.Interaction):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, msg: str):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


async def dispatch_tree(tree, interaction):
    try:
        res = tree._from_interaction(interaction)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        pass


async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # ✅ component以外はスラッシュへ渡す（超重要）
        if interaction.type != discord.InteractionType.component:
            await dispatch_tree(bot.tree, interaction)
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not custom_id:
            return

        await safe_defer(interaction)

        # -----------------------------
        # 予約ボタン
        # -----------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            if len(parts) != 4:
                await safe_send(interaction, "❌ ボタン形式エラー")
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await bot.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await bot.dm.render_panel(bot, panel_id)
            await safe_send(interaction, msg)
            return

        # -----------------------------
        # 休憩セレクト
        # -----------------------------
        if custom_id.startswith("panel:breakselect:"):
            parts = custom_id.split(":")
            panel_id = int(parts[2])
            if not values:
                await safe_send(interaction, "❌ 選択エラー")
                return

            slot_id = int(values[0])
            ok, msg = await bot.dm.toggle_break_slot(panel_id, slot_id)
            await bot.dm.render_panel(bot, panel_id)
            await safe_send(interaction, msg)
            return

        await safe_send(interaction, f"unknown custom_id: {custom_id}")

    except Exception as e:
        print("interaction error:", repr(e))
        print(traceback.format_exc())
        await safe_send(interaction, f"❌ エラー: {repr(e)}")