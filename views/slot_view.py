import discord
from utils.data_manager import load_data, save_data, get_guild

def build_panel_text(guild_data):
    lines = ["📅 予約枠"]
    for s in guild_data["slots"]:
        if s in guild_data["reservations"]:
            uid = guild_data["reservations"][s]
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

        # パネルが存在しない/別メッセージなら無視
        if not g["panel"]["message_id"]:
            await interaction.response.send_message("パネルが見つかりません。/create をやり直してね", ephemeral=True)
            return

        # 予約状態
        current = g["reservations"].get(self.slot)

        # 他人が予約済み
        if current and current != interaction.user.id:
            await interaction.response.send_message("❌ すでに埋まっています", ephemeral=True)
            return

        # 自分ならキャンセル
        if current == interaction.user.id:
            del g["reservations"][self.slot]
            # 通知済みも外す（再予約したらまた通知される）
            if self.slot in g["reminded"]:
                g["reminded"].remove(self.slot)
            save_data(data)

            await interaction.response.send_message("✅ キャンセルしました", ephemeral=True)
        else:
            # 空き→予約
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.response.send_message("✅ 予約完了", ephemeral=True)

        # パネル更新
        channel = interaction.channel
        msg = await channel.fetch_message(g["panel"]["message_id"])

        new_view = SlotView(guild_id=interaction.guild.id)
        await msg.edit(content=build_panel_text(g), view=new_view)

class SlotView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)

        data = load_data()
        g = get_guild(data, guild_id)

        # 最大25ボタン制限があるので、まずは25個まで（足りない場合はページ分け対応を後で入れる）
        for s in g["slots"][:25]:
            reserved = g["reservations"].get(s)
            self.add_item(SlotButton(s, reserved))
