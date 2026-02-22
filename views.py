import discord
from storage import load, save

class SlotView(discord.ui.View):
    def __init__(self, slot, end):
        super().__init__(timeout=None)
        self.slot = slot
        self.end = end

        data = load()
        res = data["reservations"]

        # ⭐ 初期ボタン状態
        if slot in res:
            user = res[slot]["user"]
            label = f"埋まり:{user}"
            style = discord.ButtonStyle.danger
        else:
            label = "予約する"
            style = discord.ButtonStyle.success

        self.add_item(SlotButton(slot, end, label, style))


class SlotButton(discord.ui.Button):
    def __init__(self, slot, end, label, style):
        super().__init__(label=label, style=style, custom_id=f"slot_{slot}")
        self.slot = slot
        self.end = end

    async def callback(self, interaction: discord.Interaction):

        data = load()
        res = data["reservations"]
        user = interaction.user

        # ⭐ 予約済
        if self.slot in res:
            if res[self.slot]["user"] == user.id:
                del res[self.slot]
            else:
                await interaction.response.send_message("❌ 埋まっています", ephemeral=True)
                return

        # ⭐ 予約
        else:
            res[self.slot] = {"user": user.id, "end": self.end}

        save(data)

        # ⭐ UI完全再生成
        view = SlotView(self.slot, self.end)
        await interaction.response.edit_message(view=view)
