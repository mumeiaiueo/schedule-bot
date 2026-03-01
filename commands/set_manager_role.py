import traceback
import discord
from discord import app_commands


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="set_manager_role", description="管理ロールを設定（このロール持ちは管理操作OK）")
    @app_commands.describe(role="管理に使うロール（解除したい場合は未指定で実行）")
    async def set_manager_role(interaction: discord.Interaction, role: discord.Role | None = None):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            # サーバー管理者のみ設定できるようにする
            if isinstance(interaction.user, discord.Member) and not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ サーバー管理者のみ実行できます", ephemeral=True)
                return

            ok, msg = await dm.set_manager_role_id(
                guild_id=str(interaction.guild_id),
                role_id=(role.id if role else None),
            )
            await interaction.followup.send(msg, ephemeral=True)

        except Exception:
            print("set_manager_role error")
            print(traceback.format_exc())
            try:
                await interaction.followup.send("❌ set_manager_role 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass