import discord
from typing import List, Dict
from utils.time_utils import fmt_hm


def build_panel_embed(title: str | None, day_text: str, lines: list[str]):
    e = discord.Embed(
        title=title or "募集パネル",
        description=f"{day_text}\n\n" + "\n".join(lines)
    )
    e.set_footer(text="🟢空き / 🔴予約済み（本人は押すとキャンセル） / ⚪休憩（予約不可）")
    return e


class PanelView(discord.ui.View):
    """
    ✅ callbackを使わない（B方式）
    - custom_id だけ付けて、main.py の on_interaction で処理する
    """
    def __init__(self, panel_id: int, buttons: List[Dict]):
        super().__init__(timeout=None)

        # ✅ 休憩ボタンを最後に置くので、枠ボタンは最大24にする（row 0..4 を絶対超えない）
        slot_buttons = buttons[:24]

        for i, b in enumerate(slot_buttons):
            row = min(4, i // 5)  # ✅ row エラー防止
            self.add_item(discord.ui.Button(
                label=b["label"],
                style=b["style"],
                disabled=bool(b["disabled"]),
                custom_id=f"panel:slot:{panel_id}:{int(b['slot_id'])}",
                row=row
            ))

        # ✅ 休憩切替ボタン（必ず row 4 に置く：row>=5 バグ防止）
        self.add_item(discord.ui.Button(
            label="🛠 休憩切替（管理者/管理ロール）",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
            row=4
        ))


class BreakSelectView(discord.ui.View):
    """
    ✅ Selectも callback無し（B方式）
    """
    def __init__(self, panel_id: int, options: List[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Select(
            placeholder="休憩にする/解除する時間を選んで",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"panel:breakselect:{panel_id}",
        ))