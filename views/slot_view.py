import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_guild

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))

def build_panel_text(g):
    lines = ["📅 予約枠"]
    for s in g["slots"]:
        if s in g["reservations"]:
            uid = g["reservations"][s]
            lines.append(f"🔴 {s} <@{uid}>")
        else:
            lines.append(f"🟢 {s}")
    return "\n".join(lines)


def slot_str_to_start_at_utc(g, slot_str: str) -> datetime:
    """
    g["meta"]["start_min"] と g["meta"]["cross_midnight"] を使って
    'HH:MM' を「今日(or翌日)のJST datetime」にし、UTCへ変換して返す
    """
    h, m = map(int, slot_str.split(":"))
    today_jst = datetime.now(JST).date()

    start_min = g.get("meta", {}).get("start_min")
    cross_midnight = g.get("meta", {}).get("cross_midnight", False)

    day = today_jst
    if cross_midnight and start_min is not None:
        if (h * 60 + m) < int(start_min):
            day = today_jst + timedelta(days=1)

    dt_jst = datetime(day.year, day.month, day.day, h, m, tzinfo=JST)
    return dt_jst.astimezone(timezone.utc)


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
        await interaction.response.defer(ephemeral=True)

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        current = g["reservations"].get(self.slot)

        # 他人予約済
        if current and current != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        # この枠の start_at(UTC) を計算（DB更新に使う）
        start_at_utc = slot_str_to_start_at_utc(g, self.slot)

        # DB更新（重要）
        async with interaction.client.pool.acquire() as conn:
            if current == interaction.user.id:
                # 自分ならキャンセル：DB user_id を NULL に
                await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = NULL, notified = false
                    WHERE guild_id = $1 AND start_at = $2
                    """,
                    interaction.guild.id,
                    start_at_utc
                )
            else:
                # 予約：空き（user_id IS NULL）であることを条件に更新（競合防止）
                result = await conn.execute(
                    """
                    UPDATE slots
                    SET user_id = $3, notified = false
                    WHERE guild_id = $1 AND start_at = $2 AND user_id IS NULL
                    """,
                    interaction.guild.id,
                    start_at_utc,
                    str(interaction.user.id)
                )
                # asyncpgのexecuteは "UPDATE 1" みたいな文字列を返す
                if result != "UPDATE 1":
                    await interaction.followup.send("❌ すでに埋まっています（DB側）", ephemeral=True)
                    return

        # JSON側（表示用）も更新
        if current == interaction.user.id:
            del g["reservations"][self.slot]
            if self.slot in g["reminded"]:
                g["reminded"].remove(self.slot)
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

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