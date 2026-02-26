# commands/set_manager_role.py
import discord
from discord import app_commands

from utils.discord_utils import safe_send, safe_defer

def _is_admin_only(interaction: discord.Interaction) -> bool:
    u = interaction.user
    return isinstance(u, discord.Member) and u.guild_permissions.administrator

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="set_manager_role", description="管理コマンドを使えるロールを設定（管理者のみ）")
    @app_commands.describe(role="管理ロール（例: @予約管理）")
    async def set_manager_role(interaction: discord.Interaction, role: discord.Role):
        if not _is_admin_only(interaction):
            await safe_send(interaction, "❌ このコマンドはサーバー管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)
        ok, msg = await dm.set_manager_role_id(str(interaction.guild_id), int(role.id))
        await safe_send(interaction, msg, ephemeral=True)

    @tree.command(name="clear_manager_role", description="管理ロール設定を解除（管理者のみ）")
    async def clear_manager_role(interaction: discord.Interaction):
        if not _is_admin_only(interaction):
            await safe_send(interaction, "❌ このコマンドはサーバー管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)
        ok, msg = await dm.set_manager_role_id(str(interaction.guild_id), None)
        await safe_send(interaction, msg, ephemeral=True)