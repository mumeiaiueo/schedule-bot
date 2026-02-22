import discord
from datetime import datetime, timedelta, timezone

from utils.data_manager import load_data, save_data, get_guild

SLOTS_PER_PAGE = 25
JST = timezone(timedelta(hours=9))

def build_panel_text(g):
    lines = ["📅 予約枠"]
    breaks = set(g.get("breaks", []))

    for s in g["slots"]:
        if s in breaks:
            lines.append(f"🟡 {s} 休憩")
        elif s in g["reservations"]:
            uid = g["reservations"][s]
            lines.append(f"🔴 {s} <@{uid}>")
        else:
            lines.append(f"🟢 {s}")
    return "\n".join(lines)


class SlotButton(discord.ui.Button):
    def __init__(self, slot: str, reserved_user_id: int | None, is_break: bool):
        self.slot = slot

        if is_break:
            label = f"🟡 {slot}"
            style = discord.ButtonStyle.secondary
            super().__init__(label=label, style=style, disabled=True)
            return

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

        breaks = set(g.get("breaks", []))
        if self.slot in breaks:
            await interaction.followup.send("❌ 休憩枠です", ephemeral=True)
            return

        current = g["reservations"].get(self.slot)

        # 他人予約済
        if current and current != interaction.user.id:
            await interaction.followup.send("❌ すでに埋まっています", ephemeral=True)
            return

        # ✅ DB更新は slot_time で確実に当てる（start_at完全一致のズレ事故防止）
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
                # 予約（空きのみ）
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

        # JSON側更新
        if current == interaction.user.id:
            del g["reservations"][self.slot]
            save_data(data)
            await interaction.followup.send("✅ キャンセルしました", ephemeral=True)
        else:
            g["reservations"][self.slot] = interaction.user.id
            save_data(data)
            await interaction.followup.send("✅ 予約完了", ephemeral=True)

        # パネル更新
        view = SlotView(interaction.guild.id, page=self.view.page)
        await interaction.message.edit(content=build_panel_text(g), view=view)


class BreakSelect(discord.ui.Select):
    def __init__(self, guild_id: int, page_slots: list[str], breaks: set[str]):
        options = []
        for s in page_slots:
            label = f"{s}（休憩ON）" if s in breaks else f"{s}（休憩OFF）"
            options.append(discord.SelectOption(label=label, value=s))

        super().__init__(
            placeholder="休憩にする/戻す枠を選択",
            min_values=1,
            max_values=1,
            options=options
        )
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        # 管理者チェック
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        data = load_data()
        g = get_guild(data, self.guild_id)

        slot = self.values[0]
        breaks = set(g.get("breaks", []))

        # トグル
        new_break = slot not in breaks

        async with interaction.client.pool.acquire() as conn:
            if new_break:
                # 休憩ON：予約を消して通知フラグも戻す
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

        # JSONも同期
        if new_break:
            breaks.add(slot)
            if slot in g["reservations"]:
                del g["reservations"][slot]
        else:
            breaks.discard(slot)

        g["breaks"] = sorted(list(breaks))
        save_data(data)

        await interaction.response.send_message(
            f"✅ {slot} を {'休憩ON' if new_break else '休憩OFF'} にしました",
            ephemeral=True
        )

        # パネル更新（元メッセージを更新）
        # interaction.message は Selectのメッセージなので、パネルの方を更新する必要がある
        # → 直前に押した管理ボタン側で、パネルメッセージを編集できるよう View に持たせる
        # 今回は簡単に「次のボタン操作で表示反映」でもOKですが、即時反映したい場合は下の注記参照。


class AdminBreakButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🛠 休憩切替（管理者）", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ操作できます", ephemeral=True)
            return

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        # このページの枠だけ出す（選びやすい）
        page = self.view.page
        start = page * SLOTS_PER_PAGE
        end = start + SLOTS_PER_PAGE
        page_slots = g["slots"][start:end]

        breaks = set(g.get("breaks", []))

        v = discord.ui.View(timeout=60)
        v.add_item(BreakSelect(interaction.guild.id, page_slots, breaks))
        await interaction.response.send_message("休憩を切り替える枠を選んでください：", view=v, ephemeral=True)


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

        # 管理者用：休憩切替ボタン（1個だけ）
        self.add_item(AdminBreakButton())

        if page > 0:
            self.add_item(PageButton("prev"))
        if end < len(slots):
            self.add_item(PageButton("next"))