# commands/reset_channel.py
import discord
from discord import app_commands

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer

def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.user:
        return False
    member = interaction.user
    if isinstance(member, discord.Member):
        return member.guild_permissions.administrator
    return False

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset_channel", description="このチャンネルの今日の募集パネルを削除（作り直し用）")
    async def reset_channel(interaction: discord.Interaction):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

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