# bot_interact.py
import asyncio
import traceback
import discord


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _dispatch_tree(client, interaction: discord.Interaction):
    """
    discord.py のバージョン差で process_interaction が無い/あるがあるので、
    一番安全な方法で tree に渡す
    """
    try:
        # v2系で _from_interaction が使える
        res = client.tree._from_interaction(interaction)
        if asyncio.iscoroutine(res):
            await res
        return
    except Exception:
        pass

    try:
        # もし process_interaction があるならそれを使う
        fn = getattr(client.tree, "process_interaction", None)
        if fn:
            r = fn(interaction)
            if asyncio.iscoroutine(r):
                await r
    except Exception:
        pass


async def handle_interaction(client, interaction: discord.Interaction):
    try:
        # スラッシュコマンド等は tree に渡す（ボタンとは分ける）
        if interaction.type == discord.InteractionType.application_command:
            await _dispatch_tree(client, interaction)
            return

        # component 以外は無視
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not custom_id or not isinstance(custom_id, str):
            return

        await safe_defer(interaction, ephemeral=True)

        # -------------------------
        # 予約パネル：枠ボタン
        # panel:slot:<panel_id>:<slot_id>
        # -------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            if len(parts) != 4:
                await safe_send(interaction, "❌ ボタン形式が不正です")
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await client.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await client.dm.render_panel(client, panel_id)
            await safe_send(interaction, msg)
            return

        # -------------------------
        # 休憩切替（管理者）
        # panel:breaktoggle:<panel_id>
        # -------------------------
        if custom_id.startswith("panel:breaktoggle:"):
            if not _is_admin(interaction):
                await safe_send(interaction, "❌ 管理者のみ実行できます")
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await safe_send(interaction, "❌ ボタン形式が不正です")
                return

            panel_id = int(parts[2])
            view = await client.dm.build_break_select_view(panel_id)

            try:
                await interaction.followup.send(
                    "⌚️ 休憩にする/解除する時間を選んでね👇",
                    view=view,
                    ephemeral=True,
                )
            except Exception:
                await safe_send(interaction, "❌ 表示に失敗しました（もう一度）")
            return

        # -------------------------
        # 休憩セレクト（管理者）
        # panel:breakselect:<panel_id>
        # -------------------------
        if custom_id.startswith("panel:breakselect:"):
            if not _is_admin(interaction):
                await safe_send(interaction, "❌ 管理者のみ実行できます")
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await safe_send(interaction, "❌ セレクト形式が不正です")
                return

            panel_id = int(parts[2])
            if not values:
                await safe_send(interaction, "❌ 選択値が取得できませんでした")
                return

            slot_id = int(values[0])
            ok, msg = await client.dm.toggle_break_slot(panel_id, slot_id)

            await client.dm.render_panel(client, panel_id)
            await safe_send(interaction, msg)
            return

        # その他
        await safe_send(interaction, f"unknown custom_id: {custom_id}")

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        try:
            await safe_send(interaction, f"❌ エラー: {repr(e)}")
        except Exception:
            pass