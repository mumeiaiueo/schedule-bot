import discord
from datetime import timedelta, timezone

from utils.data_manager import load_data, save_data, get_channel

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))


def build_panel_text_channel(c: dict) -> str:
    title = (c.get("title") or "").strip()
    header = f"📅 ****" if title else "📅 **予約枠**"

    lines = [header]
    breaks = set(c.get("breaks", []))
    slots = c.get("slots", [])
    reservations = c.get("reservations", {})

    for s in slots:
        if s in breaks:
            lines.append(f"⚪ {s} 休憩")
        elif s in reservations:
            uid = reservations[s]
            lines.append(f"🔴 {s} <@{uid}>")
        else:
            lines.append(f"🟢 {s}")

    return "\n".join(lines)


class SlotButtonChannel(discord.ui.Button):
    def __init__(self, channel_id: int, slot: str, reserved_user_id: int | None, is_break: bool):
        super().__init__(
            label=(f"⚪ {slot}" if is_break else f"{'🔴' if reserved_user_id else '🟢'} {slot}"),
            style=(discord.ButtonStyle.secondary if is_break else (discord.ButtonStyle.danger if reserved_user_id else discord.ButtonStyle.success)),
            disabled=is_break
        )
        self.channel_id = channel_id
        self.slot = slot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        c = get_channel(data, self.channel_id)

        breaks = set(c.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        current = c.get("reservations", {}).get(self.slot)

        # 他人が取ってる枠は取れない
        if current and current != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        # DB更新（channel_idで特定）
        async with interaction.client.pool.acquire() as conn:
            if current == interaction.user.id:
                await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = NULL, notified = false
                    WHERE channel_id = $1 AND slot_time = $2
                    """,
                    self.channel_id,
                    self.slot
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = $3, notified = false
                    WHERE channel_id = $1
                      AND slot_time = $2
                      AND user_id IS NULL
                      AND COALESCE(is_break,false) = false
                    """,
                    self.channel_id,
                    self.slot,
                    str(interaction.user.id)
                )
                if result != "UPDATE 1":
                    await interaction.followup.send("❌ すでに埋まっています（DB側）", ephemeral=True)
                    return

        # JSON同期
        c.setdefault("reservations", {})
        if current == interaction.user.id:
            c["reservations"].pop(self.slot, None)
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            c["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

        # パネル更新
        view = SlotViewChannel(channel_id=self.channel_id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text_channel(c), view=view)


class PageButton(discord.ui.Button):
    def __init__(self, direction: str):
        label = "⬅ 戻る" if direction == "prev" else "次へ ➡"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        page = self.view.page + (-1 if self.direction == "prev" else 1)

        data = load_data()
        c = get_channel(data, self.view.channel_id)

        view = SlotViewChannel(channel_id=self.view.channel_id, page=page)
        await interaction.response.edit_message(
            content=build_panel_text_channel(c),
            view=view
        )


class SlotViewChannel(discord.ui.View):
    def __init__(self, channel_id: int, page: int = 0):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.page = page

        data = load_data()
        c = get_channel(data, channel_id)

        breaks = set(c.get("breaks", []))
        slots = c.get("slots", [])

        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = slots[start:end]

        for s in page_slots:
            reserved = c.get("reservations", {}).get(s)
            self.add_item(SlotButtonChannel(channel_id, s, reserved, is_break=(s in breaks)))

        if page > 0:
            self.add_item(PageButton("prev"))
        if end < len(slots):
            self.add_item(PageButton("next"))