# views/panel_view.py ✅ B方式（main.py が custom_id を処理）用
import discord
from typing import List, Dict


def build_panel_embed(title: str | None, day_text: str, lines: list[str]):
    e = discord.Embed(
        title=title or "募集パネル",
        description=f"{day_text}\n\n" + "\n".join(lines)
    )
    e.set_footer(text="🟢空き / 🔴予約済み（本人は押すとキャンセル） / ⚪休憩（予約不可）")
    return e


class PanelView(discord.ui.View):
    """
    ✅ callback を一切持たない → 押された時の処理は main.py の on_interaction がやる

    custom_id:
      - panel:slot:<panel_id>:<slot_id>
      - panel:breaktoggle:<panel_id>
      - panel:breakselect:<panel_id>（Select）
    """
    def __init__(self, _dm_unused, panel_id: int, buttons: List[Dict]):
        super().__init__(timeout=None)

        # ✅ 休憩ボタンを入れるので、予約ボタンは最大24個（合計25）
        slot_buttons = buttons[:24]

        # slot buttons（最大24） / 5列
        for i, b in enumerate(slot_buttons):
            self.add_item(discord.ui.Button(
                label=b["label"],
                style=b["style"],
                disabled=bool(b["disabled"]),
                custom_id=f"panel:slot:{panel_id}:{int(b['slot_id'])}",
                row=i // 5,
            ))

        # 管理者用：休憩切替（最後の1枠）
        row = min(4, (len(slot_buttons) // 5))
        self.add_item(discord.ui.Button(
            label="🛠 休憩切替（管理者）",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
            row=row,
        ))


class BreakSelectView(discord.ui.View):
    """休憩選択セレクト（最大25） custom_id: panel:breakselect:<panel_id>"""
    def __init__(self, _dm_unused, panel_id: int, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Select(
            placeholder="休憩にする/解除する時間を選んで",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"panel:breakselect:{panel_id}",
        ))