import asyncio
import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):

    @tree.command(name="reset_channel", description="このチャンネルの募集を削除します（管理者のみ）")
    async def reset_channel(interaction: discord.Interaction):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ実行できます", ephemeral=True)
            return

        # まず即ACK（3秒制限回避）
        await interaction.response.defer(ephemeral=True)

        try:
            # ★ここが固まりがちなのでタイムアウトを付ける（10秒）
            await asyncio.wait_for(
                dm.delete_panel(interaction.guild.id, interaction.channel.id),
                timeout=10
            )

            await interaction.followup.send("✅ このチャンネルの募集を削除しました", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.followup.send(
                "⚠️ DB削除がタイムアウトしました（Supabase応答が遅い/固まっています）\n"
                "Renderのログにエラーが出ているはずなので確認します。",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ エラー: {repr(e)}", ephemeral=True)