import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="manager_role", description="管理ロールを設定/解除（管理者のみ）")
    async def manager_role(interaction: discord.Interaction, role: discord.Role | None = None):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("管理者のみ実行できます", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await dm.set_manager_role(interaction.guild_id, role.id if role else None)
        await interaction.followup.send(
            f"✅ 管理ロールを {'解除' if role is None else '設定: ' + role.name} しました",
            ephemeral=True
        )