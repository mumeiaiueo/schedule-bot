import traceback
import discord
from discord import app_commands


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="manager_role", description="管理ロールを設定/解除（サーバー管理者のみ）")
    @app_commands.describe(role="管理に使うロール（解除したい場合は未指定で実行）")
    async def manager_role_cmd(interaction: discord.Interaction, role: discord.Role | None = None):
        try:
            await interaction.response.defer(ephemeral=True)

            # サーバー管理者のみ
            if isinstance(interaction.user, discord.Member) and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ サーバー管理者のみ実行できます", ephemeral=True)
                return

            ok, msg = await dm.set_manager_role_id(
                guild_id=str(interaction.guild_id),
                role_id=(role.id if role else None),
            )
            await interaction.followup.send(msg, ephemeral=True)

        except Exception:
            print("manager_role error")
            print(traceback.format_exc())
            try:
                await interaction.followup.send("❌ /manager_role 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass