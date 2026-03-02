import discord
from discord import app_commands
from views.setup_wizard import build_setup_view, build_setup_embed

def register(tree: app_commands.CommandTree, dm, wizard_state: dict):
    @tree.command(name="setup", description="募集パネル作成ウィザードを開く")
    async def setup_cmd(interaction: discord.Interaction):
        st = {
            "step": 1,
            "day": "today",

            "start_hh": None,
            "start_mm": None,
            "end_hh": None,
            "end_mm": None,

            "start": None,
            "end": None,

            "interval": None,
            "title": "",
            "everyone": False,
            "notify_channel": None,

            "author_id": interaction.user.id,
        }
        wizard_state[interaction.user.id] = st

        await interaction.response.send_message(
            embed=build_setup_embed(st),
            view=build_setup_view(st),
            ephemeral=True
        )