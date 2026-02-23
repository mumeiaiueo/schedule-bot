import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_guild

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))


# =========================
# パネル表示（タイトル＋次の人）
# =========================
def build_panel_text(g):
    breaks = set(g.get("breaks", []))
    reservations = g.get("reservations", {})
    slots = g.get("slots", [])
    meta = g.get("meta", {})

    title = (g.get("title") or "").strip()
    if not title:
        title = "予約枠"

    base_date_str = meta.get("base_date", "")
    cross_midnight = bool(meta.get("cross_midnight", False))
    start_min = meta.get("start_min")  # 例: 19:00 -> 1140

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
        """HH:MM -> JST datetime（base_date + 日跨ぎ反映）"""
        if base_date is None:
            return None
        h, m = map(int, slot_str.split(":"))
        day = base_date
        if cross_midnight and start_min is not None:
            if (h * 60 + m) < int(start_min):
                day = base_date + timedelta(days=1)
        return datetime(day.year, day.month, day.day, h, m, tzinfo=JST)

    # 次の人（次の予約）を探す
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
class SlotButton(discord.ui.Button):
    def __init__(self, slot: str, reserved_user_id: int | None, is_break: bool):
        self.slot = slot

        # 休憩枠 → グレー & 押せない
        if is_break:
            super().__init__(
                label=f"⚪ {slot}",
                style=discord.ButtonStyle.secondary,
                disabled=True
            )
            return

        # 予約済 → 赤 / 空き → 緑
        if reserved_user_id:
            super().__init__(label=f"🔴 {slot}", style=discord.ButtonStyle.danger)
        else:
            super().__init__(label=f"🟢 {slot}", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        breaks = set(g.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        current = g["reservations"].get(self.slot)

        # 他人予約済
        if current and current != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        # DB更新
        async with interaction.client.pool.acquire() as conn:
            if current == interaction.user.id:
                # キャンセル
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
                # 予約（空きのみ + 休憩でない）
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

        # JSON更新（表示用）
        if current == interaction.user.id:
            del g["reservations"][self.slot]
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

        # パネル更新（現在ページ維持）
        view = SlotView(interaction.guild.id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text(g), view=view)


# =========================
# 休憩切替 Select（管理者のみ）
# =========================
class BreakSelect(discord.ui.Select):
    def __init__(self, guild_id: int, page: int, page_slots: list[str], breaks: set[str]):
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
        self.guild_id = guild_id
        self.page = page

    async def callback(self, interaction: discord.Interaction):
        # 管理者チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        data = load_data()
        g = get_guild(data, self.guild_id)

        slot = self.values[0]
        breaks = set(g.get("breaks", []))
        new_break = slot not in breaks

        # DB更新
        async with interaction.client.pool.acquire() as conn:
            if new_break:
                # 休憩ON：予約消す
                await conn.execute(
                    """
                    UPDATE slots
                    SET is_break = true, user_id = NULL, notified = false
                    WHERE guild_id = $1 AND slot_time = $2
                    """,
                    self.guild_id, slot
                )
            else:
                await conn.execute(
                    """
                    UPDATE slots
                    SET is_break = false, notified = false
                    WHERE guild_id = $1 AND slot_time = $2
                    """,
                    self.guild_id, slot
                )

        # JSON同期
        if new_break:
            breaks.add(slot)
            if slot in g.get("reservations", {}):
                del g["reservations"][slot]
        else:
            breaks.discard(slot)

        g["breaks"] = sorted(list(breaks))
        save_data(data)

        # まず結果返す（ephemeral）
        await interaction.response.send_message(
            f"✅ {slot} を {'休憩ON' if new_break else '休憩OFF'} にしました",
            ephemeral=True
        )

        # ✅ パネル（元メッセージ）を即更新
        panel = g.get("panel", {})
        ch_id = panel.get("channel_id")
        msg_id = panel.get("message_id")

        if ch_id and msg_id:
            try:
                channel = interaction.client.get_channel(ch_id)
                if channel is None:
                    channel = await interaction.client.fetch_channel(ch_id)

                message = await channel.fetch_message(msg_id)
                new_view = SlotView(self.guild_id, page=self.page)
                await message.edit(content=build_panel_text(g), view=new_view)
            except Exception:
                import traceback
                print("⚠ panel update failed")
                traceback.print_exc()


# =========================
# 休憩切替ボタン（管理者のみ）
# =========================
class AdminBreakButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛠 休憩切替（管理者）", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        page = self.view.page
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = g.get("slots", [])[start:end]
        breaks = set(g.get("breaks", []))

        v = discord.ui.View(timeout=60)
        v.add_item(BreakSelect(interaction.guild.id, page, page_slots, breaks))
        await interaction.response.send_message("休憩を切り替える枠を選んでください：", view=v, ephemeral=True)


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

        slots = g.get("slots", [])
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = slots[start:end]

        for s in page_slots:
            reserved = g.get("reservations", {}).get(s)
            self.add_item(SlotButton(s, reserved, is_break=(s in breaks)))

        # 管理者用：休憩切替ボタン
        self.add_item(AdminBreakButton())

        if page > 0:
            self.add_item(PageButton("prev"))
        if end < len(slots):
            self.add_item(PageButton("next"))