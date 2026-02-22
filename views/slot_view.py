import discord
from utils.data_manager import load_data, save_data, get_guild

SLOTS_PER_PAGE = 25

def build_panel_text(g):
    lines = ["📅 予約枠"]
    for s in g["slots"]:
        if s in g["reservations"]:
            uid = g["reservations"][s]
            lines.append(f"🔴 {s} <@{uid}>")
        else:
            lines.append(f"🟢 {s}")
    return "\n".join(lines)


class SlotButton(discord.ui.Button):
    def __init__(self, slot: str, reserved_user_id: int | None):
        self.slot = slot

        if reserved_user_id:
            label = f"🔴 {slot}"
            style = discord.ButtonStyle.danger
        else:
            label = f"🟢 {slot}"
            style = discord.ButtonStyle.success

        super().__init__(label=label, style=style)

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        g = get_guild(data, interaction.guild.id)

        current = g["reservations"].get(self.slot)

        # 他人予約済
        if current and current != interaction.user.id:
            await interaction.response.send_message("❌ すでに埋まっています", ephemeral=True)
            return

        # 自分ならキャンセル
        if current == interaction.user.id:
            del g["reservations"][self.slot]
            if self.slot in g["reminded"]:
                g["reminded"].remove(self.slot)
            save_data(data)
            await interaction.response.send_message("✅ キャンセルしました", ephemeral=True)
        else:
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.response.send_message("✅ 予約完了", ephemeral=True)

        # パネル更新（現在のページ維持）
        view = SlotView(interaction.guild.id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text(g), view=view)


class PageButton(discord.ui.Button):
    def __init__(self, direction: str):
        label = "⬅ 戻る" if direction == "prev" else "次へ ➡"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        page = self.view.page

        if self.direction == "prev":
            page -= 1
        else:
            page += 1

        view = SlotView(interaction.guild.id, page=page)
        data = load_data()
        g = get_guild(data, interaction.guild.id)

        await interaction.response.edit_message(
            content=build_panel_text(g),
            view=view
        )


class SlotView(discord.ui.View):
    def __init__(self, guild_id: int, page: int = 0):
        super().__init__(timeout=None)
        self.page = page

        data = load_data()
        g = get_guild(data, guild_id)

        slots = g["slots"]
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE

        page_slots = slots[start:end]

        for s in page_slots:
            reserved = g["reservations"].get(s)
            self.add_item(SlotButton(s, reserved))

        # ページボタン追加
        if page > 0:
            self.add_item(PageButton("prev"))

        if end < len(slots):
            self.add_item(PageButton("next"))
