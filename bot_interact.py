# bot_interact.py
print("✅ LOADED bot_interact.py v2026-02-27 split-router")

import asyncio
import traceback
import discord


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True):
    """3秒制限回避。既に応答済みなら何もしない。"""
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral)
    except Exception:
        pass


async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    """二重返信でも落ちない送信。"""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        pass


async def _dispatch_tree(bot, interaction: discord.Interaction):
    """
    ✅ スラッシュコマンド(application_command) を CommandTree に渡す
    これが無いと “応答なし” になって /setup_channel が死ぬ
    """
    try:
        res = bot.tree._from_interaction(interaction)  # discord.py内部APIだけど安定動作
        if asyncio.iscoroutine(res):
            await res
    except Exception:
        # tree側の例外はログに出しておく
        print("tree dispatch error")
        print(traceback.format_exc())


async def handle_interaction(bot, interaction: discord.Interaction):
    try:
        # -------------------------
        # 1) スラッシュコマンド等
        # -------------------------
        if interaction.type == discord.InteractionType.application_command:
            await _dispatch_tree(bot, interaction)
            return

        # -------------------------
        # 2) component（ボタン/セレクト）
        # -------------------------
        if interaction.type != discord.InteractionType.component:
            return

        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values") or []

        if not custom_id or not isinstance(custom_id, str):
            return

        print("[COMPONENT]", custom_id)

        # ✅ まずdefer（これが遅いと“応答なし”になりやすい）
        await safe_defer(interaction, ephemeral=True)

        # -------------------------
        # panel:slot:<panel_id>:<slot_id>
        # -------------------------
        if custom_id.startswith("panel:slot:"):
            parts = custom_id.split(":")
            if len(parts) != 4:
                await safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            slot_id = int(parts[3])

            ok, msg = await bot.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=getattr(interaction.user, "display_name", str(interaction.user)),
            )

            await bot.dm.render_panel(bot, panel_id)
            await safe_send(interaction, msg, ephemeral=True)
            return

        # -------------------------
        # panel:breaktoggle:<panel_id>
        # -------------------------
        if custom_id.startswith("panel:breaktoggle:"):
            if not _is_admin(interaction):
                await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await safe_send(interaction, "❌ ボタン形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            view = await bot.dm.build_break_select_view(panel_id)

            try:
                await interaction.followup.send(
                    "⌚️ 休憩にする/解除する時間を選んでね👇",
                    view=view,
                    ephemeral=True,
                )
            except Exception:
                await safe_send(interaction, "❌ 表示に失敗しました（もう一度押して）", ephemeral=True)
            return

        # -------------------------
        # panel:breakselect:<panel_id>
        # -------------------------
        if custom_id.startswith("panel:breakselect:"):
            if not _is_admin(interaction):
                await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                return

            parts = custom_id.split(":")
            if len(parts) != 3:
                await safe_send(interaction, "❌ セレクト形式が不正です", ephemeral=True)
                return

            panel_id = int(parts[2])
            if not values:
                await safe_send(interaction, "❌ 選択値が取得できませんでした", ephemeral=True)
                return

            slot_id = int(values[0])

            ok, msg = await bot.dm.toggle_break_slot(panel_id, slot_id)
            await bot.dm.render_panel(bot, panel_id)
            await safe_send(interaction, msg, ephemeral=True)
            return

        # -------------------------
        # setup ウィザード系（もし views/setup_wizard を使うならここに追加）
        # ※いまは “応答なし” を止めるのが最優先なので、
        #   setup_wizard の custom_id 処理は「次」に回してOK
        # -------------------------

        await safe_send(interaction, f"unknown custom_id: {custom_id}", ephemeral=True)

    except Exception as e:
        print("handle_interaction error:", repr(e))
        print(traceback.format_exc())
        try:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)
        except Exception:
            pass