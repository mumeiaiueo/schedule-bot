import discord
import json

DATA = "data/data.json"

def load():
    try:
        with open(DATA) as f:
            return json.load(f)
    except:
        return {}

def save(d):
    with open(DATA,"w") as f:
        json.dump(d,f)

class SlotButton(discord.ui.Button):
    def __init__(self, slot):
        super().__init__(label=f"🟢 {slot}", style=discord.ButtonStyle.success)
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        data = load()

        if self.slot in data:
            await interaction.response.send_message("予約済", ephemeral=True)
            return

        data[self.slot] = interaction.user.name
        save(data)

        self.label = f"🔴 {self.slot} {interaction.user.name}"
        self.style = discord.ButtonStyle.danger
        self.disabled = True

        await interaction.response.edit_message(view=self.view)

class SlotView(discord.ui.View):
    def __init__(self, slots):
        super().__init__(timeout=None)
        for s in slots:
            self.add_item(SlotButton(s))
