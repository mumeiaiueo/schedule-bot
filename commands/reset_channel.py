# commands/reset_channel.py
import discord
from discord import app_commands

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset_channel", description="このチャンネルの今日の募集パネルを削除（作り直し用）")
    async def reset_channel(interaction: discord.Interaction):
        # ✅ 管理者 or 管理ロール（DataManager.is_manager がある前提）
        try:
            if hasattr(dm, "is_manager"):
                if not await dm.is_manager(interaction):
                    await safe_send(interaction, "❌ 管理者（または管理ロール）のみ実行できます", ephemeral=True)
                    return
            else:
                # fallback: 管理者のみ
                member = interaction.user
                if not (isinstance(member, discord.Member) and member.guild_permissions.administrator):
                    await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
                    return
        except Exception:
            await safe_send(interaction, "❌ 権限チェックに失敗しました", ephemeral=True)
            return

        # ✅ defer（thinking=True は utils 側の実装差で落ちやすいので付けない）
        await safe_defer(interaction, ephemeral=True)

        try:
            day_date = jst_now().date()

            ok = await dm.delete_panel_by_channel_day(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day_date,
            )

            if ok:
                await safe_send(interaction, "✅ このチャンネルの募集（今日）を削除しました", ephemeral=True)
            else:
                await safe_send(interaction, "⚠️ 削除対象の募集が見つかりませんでした", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @reset_channel.error
    async def reset_channel_error(interaction: discord.Interaction, error: Exception):
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)