import discord
from discord import app_commands
from views.time_picker_view import DaySelect, HourSelect, MinuteSelect


def register(tree: app_commands.CommandTree, dm):

    @tree.command(name="setup_channel", description="UIで枠作成テスト")
    async def setup_channel(interaction: discord.Interaction):

        await interaction.response.send_message(
            "📅 今日 or 明日 を選んでください",
            view=DaySelect(callback=handle_day),
            ephemeral=True
        )


    async def handle_day(interaction: discord.Interaction, day_value: str):
        await interaction.response.edit_message(
            content=f"🕒 開始の『時』を選んでください（{day_value}）",
            view=HourSelect(callback=lambda i, h: handle_hour(i, day_value, h))
        )


    async def handle_hour(interaction: discord.Interaction, day_value: str, hour: int):
        await interaction.response.edit_message(
            content=f"🕒 {hour:02d}時 を選択。次に『分』を選んでください",
            view=MinuteSelect(hour, callback=lambda i, h, m: handle_minute(i, day_value, h, m))
        )


    async def handle_minute(interaction: discord.Interaction, day_value: str, hour: int, minute: int):
        await interaction.response.edit_message(
            content=f"✅ 開始時刻：{hour:02d}:{minute:02d}（{day_value}）",
            view=None
        )