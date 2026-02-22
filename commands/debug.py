import discord
from discord import app_commands
from utils.data_manager import load_data, get_guild

def setup(bot: discord.Client):

    @bot.tree.command(name="pingnotify", description="通知チャンネルにテスト送信")
    async def pingnotify(interaction: discord.Interaction):

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        ch_id = g.get("notify_channel")

        if not ch_id:
            await interaction.response.send_message(
                "❌ notify_channel が未設定です",
                ephemeral=True
            )
            return

        channel = bot.get_channel(int(ch_id))

        if not channel:
            await interaction.response.send_message(
                "❌ チャンネルが見つかりません（権限またはIDエラー）",
                ephemeral=True
            )
            return

        await channel.send(f"{interaction.user.mention} ✅ テスト通知です")
        await interaction.response.send_message("✅ 送信しました", ephemeral=True)
