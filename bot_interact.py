# bot_interact.py

import traceback
import discord


async def handle_component_interaction(client, interaction: discord.Interaction):
    """
    ボタン / セレクト処理専用
    """

    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")

        if not custom_id:
            return

        # 3秒制限回避
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # =============================
        # 例：panel:slot:123:456
        # =============================
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            if len(parts) != 4:
                await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await client.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await client.dm.render_panel(client, panel_id)
            await interaction.followup.send(msg, ephemeral=True)
            return

        # =============================
        # break toggle
        # =============================
        if custom_id.startswith("panel:breaktoggle:"):
            parts = custom_id.split(":")
            if len(parts) != 3:
                await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            view = await client.dm.build_break_select_view(panel_id)
            await interaction.followup.send(
                "⌚️ 休憩にする時間を選んでね👇",
                view=view,
                ephemeral=True,
            )
            return

        # =============================
        # break select
        # =============================
        if custom_id.startswith("panel:breakselect:"):
            parts = custom_id.split(":")
            if len(parts) != 3:
                await interaction.followup.send("❌ セレクト形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            values = data.get("values") or []

            if not values:
                await interaction.followup.send("❌ 選択値が取得できませんでした", ephemeral=True)
                return

            slot_id = int(values[0])
            ok, msg = await client.dm.toggle_break_slot(panel_id, slot_id)
            await client.dm.render_panel(client, panel_id)
            await interaction.followup.send(msg, ephemeral=True)
            return

    except Exception as e:
        print("handle_component_interaction error:")
        print(traceback.format_exc())
        try:
            await interaction.followup.send("❌ 内部エラー", ephemeral=True)
        except:
            pass