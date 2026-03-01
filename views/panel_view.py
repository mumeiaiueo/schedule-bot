from __future__ import annotations
import discord


def build_panel_embed(title: str | None, subtitle: str, lines: list[str]) -> discord.Embed:
    t = title or "募集パネル"
    desc = subtitle + "\n\n" + ("\n".join(lines) if lines else "（枠なし）")
    e = discord.Embed(title=t, description=desc, color=0x2B2D31)
    e.set_footer(text="🟢空き / 🔴予約済 / ⚪休憩（操作結果は実行者のみ）")
    return e


class PanelView(discord.ui.View):
    def __init__(self, panel_id: int, buttons: list[dict], notify_paused: bool):
        super().__init__(timeout=None)

        # slot buttons (最大20)
        for b in buttons[:20]:
            self.add_item(discord.ui.Button(
                label=b["label"],
                style=b["style"],
                disabled=b["disabled"],
                custom_id=f"panel:slot:{panel_id}:{b['slot_id']}",
            ))

        # row: management buttons
        self.add_item(discord.ui.Button(
            label=("🔔通知:OFF" if notify_paused else "🔔通知:ON"),
            style=(discord.ButtonStyle.secondary if notify_paused else discord.ButtonStyle.success),
            custom_id=f"panel:notifytoggle:{panel_id}",
        ))
        self.add_item(discord.ui.Button(
            label="🛠休憩切替",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
        ))


class BreakSelectView(discord.ui.View):
    def __init__(self, panel_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=120)
        self.add_item(discord.ui.Select(
            placeholder="休憩にする/解除する枠を選択",
            options=options[:25],
            min_values=1,
            max_values=1,
            custom_id=f"panel:breakselect:{panel_id}",
        ))