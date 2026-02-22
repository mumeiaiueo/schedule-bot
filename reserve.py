import json
import discord

DATA_FILE = "data.json"

# ===== JSON =====
def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"reservations": {}, "notify": {}}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

data = load_data()
reservations = data["reservations"]

# ===== View =====
class SlotView(discord.ui.View):
    def __init__(self, slot):
        super().__init__(timeout=None)
        self.slot = slot

    @discord.ui.button(label="予約する", style=discord.ButtonStyle.success)
    async def reserve(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.user

        # ⭐ 予約あり
        if self.slot in reservations:
            if reservations[self.slot] == user.id:
                # ⭐ 自分キャンセル
                del reservations[self.slot]
                data["reservations"] = reservations
                save_data(data)

                button.style = discord.ButtonStyle.success
                button.label = "予約する"
                await interaction.response.edit_message(view=self)
                return
            else:
                await interaction.response.send_message("❌ 既に予約あり", ephemeral=True)
                return

        # ⭐ 予約
        reservations[self.slot] = user.id
        data["reservations"] = reservations
        save_data(data)

        button.style = discord.ButtonStyle.danger
        button.label = f"埋まり:{user.display_name}"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="管理削除", style=discord.ButtonStyle.secondary)
    async def force_delete(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ", ephemeral=True)
            return

        if self.slot in reservations:
            del reservations[self.slot]
            data["reservations"] = reservations
            save_data(data)

        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.label.startswith("埋まり"):
                child.label = "予約する"
                child.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self)
