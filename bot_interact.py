# bot_interact.py
import asyncio
import traceback
import discord


async def _dispatch_app_command(client, interaction: discord.Interaction):
    """
    discord.py の CommandTree にスラッシュコマンドを渡す
    process_interaction が無い版でも動くように private を使う（安全に握りつぶさない）
    """
    try:
        res = client.tree._from_interaction(interaction)
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        # ここで落ちると Discord 側に応答できず「応答しない」になりやすいのでログだけ出す
        print("❌ app command dispatch error")
        print(traceback.format_exc())
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ コマンド内部エラー（ログ確認）", ephemeral=True)
        except Exception:
            pass


async def handle_component(client, interaction: discord.Interaction):
    """
    ボタン/セレクト等 component の処理
    """
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")

        if not custom_id:
            return

        # 3秒制限回避（componentは必ず先にdefer）
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        # panel:slot:<panel_id>:<slot_id>
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

        # panel:breaktoggle:<panel_id>
        if custom_id.startswith("panel:breaktoggle:"):
            parts = custom_id.split(":")
            if len(parts) != 3:
                await interaction.followup.send("❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            view = await client.dm.build_break_select_view(panel_id)
            await interaction.followup.send("⌚️ 休憩にする/解除する時間を選んでね👇", view=view, ephemeral=True)
            return

        # panel:breakselect:<panel_id>
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

        # 想定外
        await interaction.followup.send(f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception:
        print("❌ component handler error")
        print(traceback.format_exc())
        try:
            await interaction.followup.send("❌ component内部エラー（ログ確認）", ephemeral=True)
        except Exception:
            pass


async def handle_interaction(client, interaction: discord.Interaction):
    """
    MyClient.on_interaction から呼ぶ入口
    - スラッシュは tree に渡す
    - component は自前処理
    """
    if interaction.type == discord.InteractionType.application_command:
        await _dispatch_app_command(client, interaction)
        return

    if interaction.type == discord.InteractionType.component:
        await handle_component(client, interaction)
        return