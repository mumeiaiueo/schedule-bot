import traceback
import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルをセットアップ（管理者）")
    async def setup_channel(interaction: discord.Interaction):
        try:
            # ★これが最重要：3秒制限回避
            await interaction.response.defer(ephemeral=True)

            # ここから先は何秒かかってもOK（followupで返す）
            # ↓あなたの既存の処理をそのままここに入れる（dmのDB作成とか）
            res_msg = await dm.setup_channel(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                user_id=str(interaction.user.id),
            )

            await interaction.followup.send(f"✅ {res_msg}", ephemeral=True)

        except Exception as e:
            print("❌ setup_channel error:", repr(e))
            print(traceback.format_exc())
            try:
                await interaction.followup.send(f"❌ setup_channel エラー: {repr(e)}", ephemeral=True)
            except Exception:
                pass