import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_channel

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))


# =========================
# パネル表示（タイトル＋次の人）
# =========================
def build_panel_text_channel(c):
    breaks = set(c.get("breaks", []))
    reservations = c.get("reservations", {})
    slots = c.get("slots", [])
    meta = c.get("meta", {})

    title = (c.get("title") or "").strip()
    if not title:
        title = "予約枠"

    base_date_str = meta.get("base_date", "")
    cross_midnight = bool(meta.get("cross_midnight", False))
    start_min = meta.get("start_min")

    now = datetime.now(JST)

    # base_date 復元
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

    # 次の人（次の予約）
    next_info = None  # (slot_str, user_id)
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


# =========================
# 予約ボタン
# =========================
class SlotButtonChannel(discord.ui.Button):
    def __init__(self, slot: str, reserved_user_id: int | None, is_break: bool):
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

        channel_id = interaction.channel.id

        data = load_data()
        c = get_channel(data, channel_id)

        breaks = set(c.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        current = c["reservations"].get(self.slot)

        # 他人予約済
        if current and int(current) != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        # DB更新（チャンネル単位）
        async with interaction.client.pool.acquire() as conn:
            if current and int(current) == interaction.user.id:
                # キャンセル
                await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = NULL, notified = false
                    WHERE channel_id = $1 AND slot_time = $2
                    """,
                    channel_id,
                    self.slot
                )
            else:
                # 予約（空きのみ + 休憩でない）
                result = await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = $3, notified = false
                    WHERE channel_id = $1
                      AND slot_time = $2
                      AND user_id IS NULL
                      AND COALESCE(is_break,false) = false
                    """,
                    channel_id,
                    self.slot,
                    interaction.user.id   # ✅ str()禁止。intのまま
                )
                if result != "UPDATE 1":
                    await interaction.followup.send("❌ すでに埋まっています（DB側）", ephemeral=True)
                    return

        # JSON更新（表示用）
        if current and int(current) == interaction.user.id:
            del c["reservations"][self.slot]
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            c["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

        # パネル更新（現在ページ維持）
        view = SlotViewChannel(channel_id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text_channel(c), view=view)


# =========================
# 休憩切替 Select（管理者のみ）
# =========================
class BreakSelectChannel(discord.ui.Select):
    def __init__(self, channel_id: int, page: int, page_slots: list[str], breaks: set[str]):
        options = []
        for s in page_slots:
            label = f"{s}（休憩ON）" if s in breaks else f"{s}（休憩OFF）"
            options.append(discord.SelectOption(label=label, value=s))

        super().__init__(
            placeholder="休憩にする/戻す枠を選択（管理者）",
            min_values=1,
            max_values=1,
            options=options
        )
        self.channel_id = channel_id
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        data = load_data()
        c = get_channel(data, self.channel_id)

        slot = self.values[0]
        breaks = set(c.get("breaks", []))
        new_break = slot not in breaks

        async with interaction.client.pool.acquire() as conn:
            if new_break:
                await conn.execute(
                    """
                    UPDATE slots
                    SET is_break = true, user_id = NULL, notified = false
                    WHERE channel_id = $1 AND slot_time = $2
                    """,
                    self.channel_id, slot
                )
            else:
                await conn.execute(
                    """
                    UPDATE slots
                    SET is_break = false, notified = false
                    WHERE channel_id = $1 AND slot_time = $2
                    """,
                    self.channel_id, slot
                )

        if new_break:
            breaks.add(slot)
            if slot in c.get("reservations", {}):
                del c["reservations"][slot]
        else:
            breaks.discard(slot)

        c["breaks"] = sorted(list(breaks))
        save_data(data)

        await interaction.response.send_message(
            f"✅ {slot} を {'休憩ON' if new_break else '休憩OFF'} にしました",
            ephemeral=True
        )

        # パネル更新（保存してある場所を更新）
        panel = c.get("panel", {})
        ch_id = panel.get("channel_id")
        msg_id = panel.get("message_id")

        if ch_id and msg_id:
            try:
                channel = interaction.client.get_channel(ch_id) or await interaction.client.fetch_channel(ch_id)
                message = await channel.fetch_message(msg_id)
                new_view = SlotViewChannel(self.channel_id, page=self.page)
                await message.edit(content=build_panel_text_channel(c), view=new_view)
            except Exception:
                import traceback
                print("⚠ panel update failed")
                traceback.print_exc()


class AdminBreakButtonChannel(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛠 休憩切替（管理者）", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        channel_id = interaction.channel.id

        data = load_data()
        c = get_channel(data, channel_id)

        page = self.view.page
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = c.get("slots", [])[start:end]
        breaks = set(c.get("breaks", []))

        v = discord.ui.View(timeout=60)
        v.add_item(BreakSelectChannel(channel_id, page, page_slots, breaks))
        await interaction.response.send_message("休憩を切り替える枠を選んでください：", view=v, ephemeral=True)


class PageButtonChannel(discord.ui.Button):
    def __init__(self, direction: str):
        label = "⬅ 戻る" if direction == "prev" else "次へ ➡"
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        channel_id = interaction.channel.id
        page = self.view.page + (-1 if self.direction == "prev" else 1)

        view = SlotViewChannel(channel_id, page=page)
        data = load_data()
        c = get_channel(data, channel_id)

        await interaction.response.edit_message(
            content=build_panel_text_channel(c),
            view=view
        )


class SlotViewChannel(discord.ui.View):
    def __init__(self, channel_id: int, page: int = 0):
        super().__init__(timeout=None)
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
            reserved_int = int(reserved) if reserved is not None else None
            self.add_item(SlotButtonChannel(s, reserved_int, is_break=(s in breaks)))

        self.add_item(AdminBreakButtonChannel())

        if page > 0:
            self.add_item(PageButtonChannel("prev"))
        if end < len(slots):
            self.add_item(PageButtonChannel("next"))