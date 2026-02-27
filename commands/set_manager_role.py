# commands/set_manager_role.py
import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="set_manager_role", description="管理ロールを設定/解除します（管理者のみ）")
    @app_commands.describe(role="管理ロール（解除する場合は未指定）")
    async def set_manager_role(interaction: discord.Interaction, role: discord.Role | None = None):
        # ✅ まず defer（これがないと“考え中”で止まりやすい）
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception:
            pass

        # ✅ 管理者チェック（ここも defer 後にやると安全）
        m = interaction.user
        if not isinstance(m, discord.Member) or not m.guild_permissions.administrator:
            try:
                await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
            except Exception:
                pass
            return

        if not interaction.guild_id:
            try:
                await interaction.followup.send("❌ サーバー内で実行してね", ephemeral=True)
            except Exception:
                pass
            return

        # ✅ 設定/解除
        try:
            ok, msg = await dm.set_manager_role_id(
                guild_id=str(interaction.guild_id),
                role_id=(int(role.id) if role else None),
            )
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ DBエラー: {repr(e)}", ephemeral=True)
            except Exception:
                pass
            return

        # ✅ 最後に必ず返す（ここが無いと“考え中”のまま）
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass