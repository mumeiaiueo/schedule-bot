import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_guild

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))


# =========================
# パネル表示（タイトル＋次の人対応版）
# =========================
def build_panel_text(g):
    breaks = set(g.get("breaks", []))
    reservations = g.get("reservations", {})
    slots = g.get("slots", [])
    meta = g.get("meta", {})
    title = g.get("title") or "予約枠"

    base_date_str = meta.get("base_date")
    cross_midnight = meta.get("cross_midnight", False)
    start_min = meta.get("start_min")

    now = datetime.now(JST)

    # --- 日付復元 ---
    base_date = None
    if base_date_str:
        try:
            y, m, d = map(int, base_date_str.split("-"))
            base_date = datetime(y, m, d, tzinfo=JST).date()
        except:
            pass

    def slot_to_dt(slot_str):
        if base_date is None:
            return None
        h, m = map(int, slot_str.split(":"))
        day = base_date
        if cross_midnight and start_min is not None:
            if (h * 60 + m) < int(start_min):
                day = base_date + timedelta(days=1)
        return datetime(day.year, day.month, day.day, h, m, tzinfo=JST)

    # --- 次の人判定 ---
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

    # --- 表示構築 ---
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


# =========================
# 予約ボタン
# =========================
class SlotButton(discord.ui.Button):
    def __init__(self, slot: str, reserved_user_id: int | None, is_break: bool):
        self.slot = slot

        if is_break:
            super().__init__(
                label=f"⚪ {slot}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            return

        if reserved_user_id:
            super().__init__(
                label=f"🔴 {slot}",
                style=discord.ButtonStyle.danger
            )
        else:
            super().__init__(
                label=f"🟢 {slot}",
                style=discord.ButtonStyle.success
            )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        breaks = set(g.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        current = g["reservations"].get(self.slot)

        if current and current != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        async with interaction.client.pool.acquire() as conn:
            if current == interaction.user.id:
                await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = NULL, notified = false
                    WHERE guild_id = $1 AND slot_time = $2
                    """,
                    interaction.guild.id,
                    self.slot
                )
            else:
                result = await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = $3, notified = false
                    WHERE guild_id = $1
                      AND slot_time = $2
                      AND user_id IS NULL
                      AND COALESCE(is_break,false) = false
                    """,
                    interaction.guild.id,
                    self.slot,
                    str(interaction.user.id)
                )
                if result != "UPDATE 1":
                    await interaction.followup.send("❌ すでに埋まっています（DB側）", ephemeral=True)
                    return

        if current == interaction.user.id:
            del g["reservations"][self.slot]
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

        view = SlotView(interaction.guild.id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text(g), view=view)


# =========================
# ページボタン
# =========================
class PageButton(discord.ui.Button):
    def __init__(self, direction: str):
        label = "⬅ 戻る" if direction == "prev" else "次へ ➡"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        page = self.view.page + (-1 if self.direction == "prev" else 1)

        view = SlotView(interaction.guild.id, page=page)
        data = load_data()
        g = get_guild(data, interaction.guild.id)

        await interaction.response.edit_message(
            content=build_panel_text(g),
            view=view
        )


# =========================
# View本体
# =========================
class SlotView(discord.ui.View):
    def __init__(self, guild_id: int, page: int = 0):
        super().__init__(timeout=None)
        self.page = page

        data = load_data()
        g = get_guild(data, guild_id)

        breaks = set(g.get("breaks", []))

        slots = g["slots"]
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = slots[start:end]

        for s in page_slots:
            reserved = g["reservations"].get(s)
            self.add_item(SlotButton(s, reserved, is_break=(s in breaks)))

        if page > 0:
            self.add_item(PageButton("prev"))
        if end < len(slots):
            self.add_item(PageButton("next"))