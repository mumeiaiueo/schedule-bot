import discord
from discord.ui import View, Button
from reserve import load_data, save_data


class SlotButton(Button):
    def __init__(self, slot):
        super().__init__(label=f"🟢 {slot}", style=discord.ButtonStyle.success)
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        data = load_data()

        # 予約済チェック
        if self.slot in data:
            await interaction.response.send_message("❌ 予約済", ephemeral=True)
            return

        # 予約登録
        data[self.slot] = interaction.user.name
        save_data(data)

        # ボタン更新
        self.label = f"🔴 {self.slot} ({interaction.user.name})"
        self.style = discord.ButtonStyle.danger
        self.disabled = True

        await interaction.response.edit_message(view=self.view)


class SlotView(View):
    def __init__(self, slots):
        super().__init__(timeout=None)
        for s in slots:
            self.add_item(SlotButton(s))
