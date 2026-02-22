import discord
from discord import app_commands
from utils.data_manager import load_data, save_data, get_guild

def setup(bot: discord.Client):

    @bot.tree.command(name="notifyset", description="3分前通知のチャンネルを設定（未設定なら通知なし）")
    @app_commands.checks.has_permissions(administrator=True)
    async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        g = get_guild(data, interaction.guild.id)
        g["notify_channel"] = channel.id
        save_data(data)

        await interaction.followup.send(f"✅ 通知チャンネルを {channel.mention} に設定しました", ephemeral=True)
