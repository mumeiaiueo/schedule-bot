# views/panel_view.py
import discord


def build_panel_embed(title: str | None, day_text: str, lines: list[str]) -> discord.Embed:
    e = discord.Embed(title=title or "募集パネル", description=f"{day_text}\n\n" + "\n".join(lines))
    e.set_footer(text="🟢空き / 🔴予約済み / ⚪休憩（次の段階で実装）")
    return e


class PanelView(discord.ui.View):
    # 次の段階で予約/休憩/通知ボタンに拡張する
    def __init__(self):
        super().__init__(timeout=None)