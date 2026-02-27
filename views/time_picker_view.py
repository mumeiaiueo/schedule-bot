import discord
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


class DaySelect(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=180)
        self.callback = callback

    @discord.ui.button(label="今日", style=discord.ButtonStyle.primary)
    async def today(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, "today")

    @discord.ui.button(label="明日", style=discord.ButtonStyle.secondary)
    async def tomorrow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.callback(interaction, "tomorrow")


class HourSelect(discord.ui.View):
    def __init__(self, callback):
        super().__init__(timeout=180)
        self.callback = callback

        select = discord.ui.Select(
            placeholder="開始の「時」を選んでください",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=f"{h:02d}時", value=str(h))
                for h in range(24)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        hour = int(interaction.data["values"][0])
        await self.callback(interaction, hour)


class MinuteSelect(discord.ui.View):
    def __init__(self, hour: int, callback):
        super().__init__(timeout=180)
        self.hour = hour
        self.callback = callback

        select = discord.ui.Select(
            placeholder="開始の「分」を選んでください",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label=f"{hour:02d}:{m:02d}", value=str(m))
                for m in range(0, 60, 5)
            ]
        )
        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        minute = int(interaction.data["values"][0])
        await self.callback(interaction, self.hour, minute)