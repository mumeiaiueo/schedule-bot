# commands/setup_channel.py
import discord
from discord import app_commands
from views.setup_wizard import build_setup_embed, build_setup_view

def register(tree: app_commands.CommandTree, dm):

    @tree.command(name="setup_channel", description="募集枠をボタンで作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        # セッション初期化は main 側で持つので、ここは表示だけ
        await interaction.response.send_message(
            "📅 今日 or 明日 を選んでください",
            embed=build_setup_embed({}),
            view=build_setup_view({}),
            ephemeral=True
        )