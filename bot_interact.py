# bot_interact.py
print("🔥 BOOT bot_interact.py v2026-02-28 STABLE 🔥")

import asyncio
import traceback
import discord


async def _safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def _safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _dispatch_tree(bot, interaction: discord.Interaction):
    """
    discord.py のバージョン差分を吸収して Tree に渡す
    """
    try:
        if hasattr(bot.tree, "process_interaction"):
            coro = bot.tree.process_interaction(interaction)
            if asyncio.iscoroutine(coro):
                await coro
            return

        # process_interaction が無い環境でも動くように
        if hasattr(bot.tree, "_from_interaction"):
            res = bot.tree._from_interaction(interaction)
            if asyncio.iscoroutine(res):
                await res
            return

        await _safe_send(interaction, "❌ この環境のdiscord.pyが古い/違う可能性があります", ephemeral=True)

    except Exception:
        # Tree が例外吐いても落とさない
        print("tree dispatch error")
        print(traceback.format_exc())


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # 1) スラッシュコマンド等は Tree に渡す
        if interaction.type == discord.InteractionType.application_command:
            await _dispatch_tree(bot, interaction)
            return

        # 2) component以外は無視
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not isinstance(custom_id, str) or not custom_id:
            return

        # 3) 3秒制限回避（ここが “応答なし” 対策の要）
        await _safe_defer(interaction, ephemeral=True)

        # -------------------------
        # 既存: panel ボタン
        # -------------------------
        if custom_id.startswith("panel:slot:"):
            # panel:slot:<panel_id>:<slot_id>
            parts = custom_id.split(":")
            if len(parts) != 4:
                await _safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await bot.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await bot.dm.render_panel(bot, panel_id)
            await _safe_send(interaction, msg, ephemeral=True)
            return

        if custom_id.startswith("panel:breaktoggle:"):
            if not _is_admin(interaction):
                await _safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await _safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            view = await bot.dm.build_break_select_view(panel_id)
            await interaction.followup.send(
                "⌚️ 休憩にする/解除する時間を選んでね👇",
                view=view,
                ephemeral=True,
            )
            return

        if custom_id.startswith("panel:breakselect:"):
            if not _is_admin(interaction):
                await _safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await _safe_send(interaction, "❌ セレクト形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            if not values:
                await _safe_send(interaction, "❌ 選択値が取得できませんでした", ephemeral=True)
                return

            slot_id = int(values[0])
            ok, msg = await bot.dm.toggle_break_slot(panel_id, slot_id)
            await bot.dm.render_panel(bot, panel_id)
            await _safe_send(interaction, msg, ephemeral=True)
            return

        # それ以外（setupウィザード等）は Tree 側が扱うなら Tree に流す
        # （今後 setup: をここで処理したくなったらここに足せる）
        await _safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        await _safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)