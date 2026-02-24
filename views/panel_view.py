import discord

def build_panel_embed(title: str | None, day_text: str, lines: list[str]):
    e = discord.Embed(
        title=title or "募集パネル",
        description=f"{day_text}\n\n" + ("\n".join(lines) if lines else "枠がありません")
    )
    e.set_footer(text="🟢空き / 🔴予約済み（本人は押すとキャンセル） / ⚪休憩")
    return e

class PanelView(discord.ui.View):
    """
    custom_id:
      panel:slot:<panel_id>:<slot_id>
      panel:breaktoggle:<panel_id>
    """
    def __init__(self, panel_id: int, buttons: list[dict]):
        super().__init__(timeout=None)

        # slot buttons (最大25) / 5列
        for i, b in enumerate(buttons[:25]):
            self.add_item(discord.ui.Button(
                label=b["label"],
                style=b["style"],
                disabled=b["disabled"],
                custom_id=f"panel:slot:{panel_id}:{b['slot_id']}",
                row=min(4, i // 5),
            ))

        # 管理者用：休憩切替
        self.add_item(discord.ui.Button(
            label="🛠 休憩切替（管理者）",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
            row=4
        ))

class BreakSelectView(discord.ui.View):
    """
    custom_id:
      panel:breakselect:<panel_id>
    """
    def __init__(self, panel_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=60)
        self.add_item(discord.ui.Select(
            placeholder="休憩にする/解除する時間を選んで",
            min_values=1,
            max_values=1,
            options=options[:25],
            custom_id=f"panel:breakselect:{panel_id}",
        ))