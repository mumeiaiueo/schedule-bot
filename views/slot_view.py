import discord
from utils.data_manager import load_data, save_data, get_guild

async def refresh_panel(interaction: discord.Interaction):
    data = load_data()
    g = get_guild(data, interaction.guild.id)

    ch_id = g.get("panel_channel_id")
    msg_id = g.get("panel_message_id")
    if not ch_id or not msg_id:
        return

    channel = interaction.client.get_channel(int(ch_id))
    if not channel:
        return

    try:
        message = await channel.fetch_message(int(msg_id))
    except Exception:
        return

    # 表示テキスト生成
    lines = ["📅 予約枠"]
    for s in g["slots"]:
        hhmm = s["start_iso"][11:16]
        sid = s["id"]
        if sid in g["reservations"]:
            uid = g["reservations"][sid]
            lines.append(f"🔴 {hhmm} <@{uid}>")
        else:
            lines.append(f"🟢 {hhmm}")

    await message.edit(content="\n".join(lines), view=SlotView(interaction.guild.id))
    save_data(data)

class SlotButton(discord.ui.Button):
    def __init__(self, guild_id: int, slot: dict):
        self.guild_id = guild_id
        self.slot = slot

        hhmm = slot["start_iso"][11:16]
        super().__init__(
            label=f"🟢 {hhmm}",
            style=discord.ButtonStyle.success,
            custom_id=f"slot:{guild_id}:{slot['id']}"
        )

    async def callback(self, interaction: discord.Interaction):
        data = load_data()
        g = get_guild(data, interaction.guild.id)

        slot_id = self.slot["id"]
        reservations = g["reservations"]

        # 予約済み
        if slot_id in reservations:
            # 自分ならキャンセル
            if reservations[slot_id] == interaction.user.id:
                del reservations[slot_id]
                if slot_id in g["reminded"]:
                    g["reminded"].remove(slot_id)
                save_data(data)

                await interaction.response.send_message("キャンセルしました", ephemeral=True)
                await refresh_panel(interaction)
                return

            await interaction.response.send_message("埋まっています", ephemeral=True)
            return

        # 空き → 予約（早い者勝ち）
        reservations[slot_id] = interaction.user.id
        save_data(data)

        await interaction.response.send_message("予約完了", ephemeral=True)
        await refresh_panel(interaction)

class SlotView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)

        data = load_data()
        g = get_guild(data, int(guild_id))

        # ボタン追加
        for s in g["slots"]:
            self.add_item(SlotButton(int(guild_id), s))

        # ラベル/色を予約状況に合わせる
        reservations = g["reservations"]
        for item in self.children:
            if isinstance(item, SlotButton):
                sid = item.slot["id"]
                hhmm = item.slot["start_iso"][11:16]
                if sid in reservations:
                    uid = reservations[sid]
                    item.style = discord.ButtonStyle.danger
                    item.label = f"🔴 {hhmm} <@{uid}>"
                else:
                    item.style = discord.ButtonStyle.success
                    item.label = f"🟢 {hhmm}"
