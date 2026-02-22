import discord
from discord import app_commands
from datetime import datetime
from utils.time_utils import generate_slots
from views.slot_view import SlotView

def setup(bot):

    @bot.tree.command(name="create")
    @app_commands.choices(interval=[
        app_commands.Choice(name="20", value=20),
        app_commands.Choice(name="25", value=25),
        app_commands.Choice(name="30", value=30),
    ])
    async def create(interaction: discord.Interaction,
                     start:str,
                     end:str,
                     interval:app_commands.Choice[int]):

        start_dt = datetime.strptime(start,"%H:%M")
        end_dt = datetime.strptime(end,"%H:%M")

        slots = generate_slots(start_dt,end_dt,interval.value)

        msg = "📅予約枠\n"
        for s in slots:
            msg += f"🟢 {s}\n"

        await interaction.response.send_message(msg,view=SlotView(slots))
