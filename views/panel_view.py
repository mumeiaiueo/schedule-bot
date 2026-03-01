from __future__ import annotations

import discord


# =============================
# Embed builder
# =============================
def build_panel_embed(title: str | None, subtitle: str, lines: list[str]) -> discord.Embed:
    t = title.strip() if isinstance(title, str) and title.strip() else "募集パネル"
    desc = subtitle + "\n\n" + ("\n".join(lines) if lines else "（枠がありません）")

    e = discord.Embed(
        title=t,
        description=desc,
        color=0x57F287,
    )
    e.set_footer(text="🟢空き / 🔴予約済み / ⚪休憩（予約不可）")
    return e


# =============================
# Panel View（枠ボタン＋管理ボタン）
# =============================
class PanelView(discord.ui.View):
    def __init__(self, panel_id: int, buttons: list[dict], notify_paused: bool = False):
        super().__init__(timeout=None)

        # --- 枠ボタン（最大20想定） ---
        for b in buttons:
            slot_id = int(b["slot_id"])
            label = str(b["label"])
            style = b.get("style", discord.ButtonStyle.secondary)
            disabled = bool(b.get("disabled", False))

            btn = discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                custom_id=f"panel:slot:{panel_id}:{slot_id}",
            )
            # callbackはbot_interact.py側で処理するのでnoop
            btn.callback = self._noop
            self.add_item(btn)

        # --- 管理ボタン ---
        # 通知ON/OFF（3分前通知の停止/再開）
        notify_label = "🔕 通知OFF" if not notify_paused else "🔔 通知ON"
        notify_btn = discord.ui.Button(
            label=notify_label,
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:notifytoggle:{panel_id}",
            row=4,
        )
        notify_btn.callback = self._noop
        self.add_item(notify_btn)

        # 休憩切替（selectを開く）
        break_btn = discord.ui.Button(
            label="🛠 休憩切替",
            style=discord.ButtonStyle.secondary,
            custom_id=f"panel:breaktoggle:{panel_id}",
            row=4,
        )
        break_btn.callback = self._noop
        self.add_item(break_btn)

    async def _noop(self, interaction: discord.Interaction):
        return


# =============================
# Break Select View（休憩にする枠を選ぶ）
# =============================
class BreakSelectView(discord.ui.View):
    def __init__(self, panel_id: int, options: list[discord.SelectOption]):
        super().__init__(timeout=120)

        sel = discord.ui.Select(
            placeholder="休憩にする/解除する時間を選んでください（トグル）",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"panel:breakselect:{panel_id}",
        )
        sel.callback = self._noop
        self.add_item(sel)

    async def _noop(self, interaction: discord.Interaction):
        return