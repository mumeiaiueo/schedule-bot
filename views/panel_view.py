# views/panel_view.py
import discord
from typing import List, Dict, Optional

from utils.time_utils import fmt_hm


def build_panel_embed(title: str | None, day_text: str, lines: list[str]):
    e = discord.Embed(
        title=title or "募集パネル",
        description=f"{day_text}\n\n" + "\n".join(lines)
    )
    e.set_footer(text="🟢空き / 🔴予約済み（本人は押すとキャンセル） / ⚪休憩（予約不可）")
    return e


async def _respond(interaction: discord.Interaction, content: str, *, ephemeral: bool = True, view=None):
    """二重返信でも落ちない send"""
    try:
        await interaction.response.send_message(content, ephemeral=ephemeral, view=view)
    except discord.InteractionResponded:
        await interaction.followup.send(content, ephemeral=ephemeral, view=view)


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


class SlotButton(discord.ui.Button):
    def __init__(self, dm, panel_id: int, slot_id: int, label: str, style: discord.ButtonStyle, disabled: bool, row: int):
        super().__init__(
            label=label,
            style=style,
            disabled=disabled,
            custom_id=f"panel:slot:{panel_id}:{slot_id}",
            row=row
        )
        self.dm = dm
        self.panel_id = panel_id
        self.slot_id = slot_id

    async def callback(self, interaction: discord.Interaction):
        ok, msg = await self.dm.toggle_reserve(
            slot_id=int(self.slot_id),
            user_id=str(interaction.user.id),
            user_name=getattr(interaction.user, "display_name", str(interaction.user)),
        )
        # パネル再描画（表示更新）
        await self.dm.render_panel(interaction.client, int(self.panel_id))
        await _respond(interaction, msg, ephemeral=True)


class BreakToggleButton(discord.ui.Button):
    def __init__(self, dm, panel_id: int, row: int):
        super().__init__(
            label="🛠 休憩切替（管理者）",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
            row=row
        )
        self.dm = dm
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        if not _is_admin(interaction):
            await _respond(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        view = await self.dm.build_break_select_view(int(self.panel_id))
        await _respond(interaction, "休憩にする/解除する時間を選んでね👇", ephemeral=True, view=view)


class BreakSelect(discord.ui.Select):
    def __init__(self, dm, panel_id: int, options: List[discord.SelectOption]):
        super().__init__(
            placeholder="休憩にする/解除する時間を選んで",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"panel:breakselect:{panel_id}",
        )
        self.dm = dm
        self.panel_id = panel_id

    async def callback(self, interaction: discord.Interaction):
        if not _is_admin(interaction):
            await _respond(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        if not self.values:
            await _respond(interaction, "❌ 選択値が取得できませんでした", ephemeral=True)
            return

        slot_id = int(self.values[0])
        ok, msg = await self.dm.toggle_break_slot(int(self.panel_id), slot_id)

        # パネル再描画（表示更新）
        await self.dm.render_panel(interaction.client, int(self.panel_id))
        await _respond(interaction, msg, ephemeral=True)


class BreakSelectView(discord.ui.View):
    def __init__(self, dm, panel_id: int, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(BreakSelect(dm, panel_id, options))


class PanelView(discord.ui.View):
    """
    slot button: panel:slot:<panel_id>:<slot_id>
    break toggle: panel:breaktoggle:<panel_id>
    """
    def __init__(self, dm, panel_id: int, buttons: List[Dict]):
        super().__init__(timeout=None)

        # slot buttons (最大25) / 5列
        for i, b in enumerate(buttons[:25]):
            self.add_item(SlotButton(
                dm=dm,
                panel_id=panel_id,
                slot_id=int(b["slot_id"]),
                label=b["label"],
                style=b["style"],
                disabled=bool(b["disabled"]),
                row=i // 5,
            ))

        # 管理者用：休憩切替ボタン
        row = min(4, (len(buttons[:25]) // 5) + 1)
        self.add_item(BreakToggleButton(dm=dm, panel_id=panel_id, row=row))