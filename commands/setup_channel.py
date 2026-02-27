# commands/setup_channel.py
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルで枠作成ウィザードを開く（ボタン式）")
    async def setup_channel(interaction: discord.Interaction):
        # ✅ 自分だけに表示（スクショの形式）
        bot = interaction.client
        st = bot.get_setup_state(interaction.user.id)

        embed = build_setup_embed(st)
        view = build_setup_view(st)

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)