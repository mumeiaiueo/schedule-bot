import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_channel

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))


def build_panel_text_channel(c: dict) -> str:
    breaks = set(c.get("breaks", []))
    reservations = c.get("reservations", {})
    slots = c.get("slots", [])
    meta = c.get("meta", {})

    title = (c.get("title") or "").strip() or "予約枠"

    base_date_str = meta.get("base_date", "")
    cross_midnight = bool(meta.get("cross_midnight", False))
    start_min = meta.get("start_min")

    now = datetime.now(JST)

    base_date = None
    if base_date_str:
        try:
            y, m, d = map(int, base_date_str.split("-"))
            base_date = datetime(y, m, d, tzinfo=JST).date()
        except Exception:
            base_date = None

    def slot_to_dt(slot_str: str):
        if base_date is None:
            return None
        h, m = map(int, slot_str.split(":"))
        day = base_date
        if cross_midnight and start_min is not None:
            if (h * 60 + m) < int(start_min):
                day = base_date + timedelta(days=1)
        return datetime(day.year, day.month, day.day, h, m, tzinfo=JST)

    # 次の人
    next_info = None
    for s in slots:
        if s in breaks:
            continue
        uid = reservations.get(s)
        if not uid:
            continue
        dt = slot_to_dt(s)
        if dt and dt >= now:
            next_info = (s, uid)
            break

    lines = []
    lines.append("━━━━━━━━━━━━━━━━")
    lines.append(f"🎨 **【 {title} 】**")
    if base_date_str:
        lines.append(f"📅 {base_date_str}")
    lines.append("━━━━━━━━━━━━━━━━")

    if next_info:
        s, uid = next_info
        lines.append(f"⏳ 次の人：**{s}** <@{uid}>")
    else:
        lines.append("⏳ 次の人：なし")

    lines.append("━━━━━━━━━━━━━━━━")

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
    def __init__(self, channel_id: int, slot: str, reserved_user_id: str | None, is_break: bool):
        self.channel_id = channel_id
        self.slot = slot

        if is_break:
            super().__init__(label=f"⚪ {slot}", style=discord.ButtonStyle.secondary, disabled=True)
            return

        if reserved_user_id:
            super().__init__(label=f"🔴 {slot}", style=discord.ButtonStyle.danger)
        else:
            super().__init__(label=f"🟢 {slot}", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        c = get_channel(data, self.channel_id)

        breaks = set(c.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        # JSON側の現在値（表示用）
        current = c.get("reservations", {}).get(self.slot)

        async with interaction.client.pool.acquire() as conn:
            if current and str(current) == str(interaction.user.id):
                # キャンセル（チャンネル単位）
                await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = NULL, notified = false
                    WHERE channel_id = $1 AND slot_time = $2
                    """,
                    int(self.channel_id),
                    self.slot
                )
                # JSON更新
                del c["reservations"][self.slot]
                save_data(data)
                await interaction.followup.send("✅ キャンセルしました", ephemeral=True)

            else:
                # 予約（空きのみ）
                result = await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = $3, notified = false
                    WHERE channel_id = $1
                      AND slot_time = $2
                      AND user_id IS NULL
                      AND COALESCE(is_break,false) = false
                    """,
                    int(self.channel_id),
                    self.slot,
                    str(interaction.user.id)  # user_id列がtext想定
                )
                if result != "UPDATE 1":
                    await interaction.followup.send("❌ すでに埋まっています（DB側）", ephemeral=True)
                    return

                c.setdefault("reservations", {})
                c["reservations"][self.slot] = str(interaction.user.id)
                save_data(data)
                await interaction.followup.send("✅ 予約完了", ephemeral=True)

        # パネル更新（同じページ維持）
        view = SlotViewChannel(channel_id=self.channel_id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text_channel(c), view=view)


class PageButtonChannel(discord.ui.Button):
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
        self.channel_id = int(channel_id)
        self.page = page

        data = load_data()
        c = get_channel(data, self.channel_id)

        breaks = set(c.get("breaks", []))
        slots = c.get("slots", [])

        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = slots[start:end]

        reservations = c.get("reservations", {})

        for s in page_slots:
            reserved = reservations.get(s)  # text想定
            self.add_item(SlotButtonChannel(self.channel_id, s, reserved, is_break=(s in breaks)))

        if page > 0:
            self.add_item(PageButtonChannel("prev"))
        if end < len(slots):
            self.add_item(PageButtonChannel("next"))