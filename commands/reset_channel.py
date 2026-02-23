import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):

    @tree.command(name="reset_channel", description="このチャンネルの募集を削除します（管理者のみ）")
    async def reset_channel(interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ 管理者のみ実行できます",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            await dm.delete_panel(interaction.guild.id, interaction.channel.id)

            await interaction.followup.send(
                "✅ このチャンネルの募集を削除しました",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ エラーが発生しました\n{repr(e)}",
                ephemeral=True
            )