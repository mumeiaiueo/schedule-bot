# views/panel_view.py
from __future__ import annotations

import discord
from typing import List, Dict


def build_panel_embed(title: str | None, day_text: str, lines: list[str]):
    e = discord.Embed(
        title=title or "募集パネル",
        description=f"{day_text}\n\n" + "\n".join(lines) if lines else day_text
    )
    e.set_footer(text="🟢空き / 🔴予約済み（本人は押すとキャンセル） / ⚪休憩（予約不可）")
    return e


class PanelView(discord.ui.View):
    """
    ✅ callbackを使わない（B方式）
    - custom_id だけ付けて、bot_app.py の on_interaction → bot_interact.py で処理
    """
    def __init__(self, panel_id: int, buttons: List[Dict], notify_paused: bool = False):
        super().__init__(timeout=None)

        # ✅ row4 を管理ボタン専用にするので、枠ボタンは最大20（row0..3）
        slot_buttons = (buttons or [])[:20]

        for i, b in enumerate(slot_buttons):
            row = i // 5  # 0..3
            label = str(b.get("label", ""))
            style = b.get("style", discord.ButtonStyle.secondary)
            disabled = bool(b.get("disabled", False))
            slot_id = int(b["slot_id"])

            self.add_item(discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                custom_id=f"panel:slot:{panel_id}:{slot_id}",
                row=row
            ))

        # ✅ 通知 ON/OFF（管理者/管理ロール）
        notify_style = discord.ButtonStyle.secondary if notify_paused else discord.ButtonStyle.success
        notify_label = "🔕 通知OFF" if notify_paused else "🔔 通知ON"

        self.add_item(discord.ui.Button(
            label=notify_label,
            style=notify_style,
            custom_id=f"panel:notifytoggle:{panel_id}",
            row=4
        ))

        # ✅ 休憩切替（管理者/管理ロール）
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
            options=(options or [])[:25],
            custom_id=f"panel:breakselect:{panel_id}",
        ))