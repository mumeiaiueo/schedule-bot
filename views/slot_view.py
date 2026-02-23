import discord

class SlotView(discord.ui.View):
    def __init__(self, channel_id: int):
        super().__init__(timeout=None)
        self.channel_id = channel_id

        self.add_item(
            discord.ui.Button(
                label="テストボタン",
                style=discord.ButtonStyle.success
            )
        )

def build_panel_text():
    return "予約パネル"