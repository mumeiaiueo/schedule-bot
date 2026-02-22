import discord
from discord import app_commands
from utils.data_manager import load_data, save_data, get_guild

def setup(bot: discord.Client):

    @bot.tree.command(name="remindset", description="3分前通知を送るチャンネルを設定")
    @app_commands.checks.has_permissions(administrator=True)
    async def remindset(interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_data()
        g = get_guild(data, interaction.guild.id)
        g["remind_channel_id"] = channel.id
        save_data(data)
        await interaction.response.send_message("✅ 3分前通知チャンネルを設定しました", ephemeral=True)

    @bot.tree.command(name="remindoff", description="3分前通知をOFF")
    @app_commands.checks.has_permissions(administrator=True)
    async def remindoff(interaction: discord.Interaction):
        data = load_data()
        g = get_guild(data, interaction.guild.id)
        g["remind_channel_id"] = None
        save_data(data)
        await interaction.response.send_message("✅ 3分前通知をOFFにしました", ephemeral=True)
