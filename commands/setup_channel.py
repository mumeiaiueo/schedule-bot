# commands/setup_channel.py
import discord

def register(tree: discord.app_commands.CommandTree, bot_client):
    @tree.command(name="setup_channel", description="このチャンネルで募集パネルを作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        # すぐ返す（反応しません対策）
        await bot_client.start_setup_wizard(interaction)