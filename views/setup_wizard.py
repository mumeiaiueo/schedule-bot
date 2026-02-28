# views/setup_wizard.py
from __future__ import annotations

import discord


def build_setup_embed(st: dict) -> discord.Embed:
    # st は {"day","start","end","interval","notify_channel_id","everyone","title"} など
    day = "今日" if st.get("day") == "today" else "明日" if st.get("day") == "tomorrow" else "未設定"
    start = st.get("start") or "--:--"
    end = st.get("end") or "--:--"
    interval = f"{st.get('interval')}分" if st.get("interval") else "未設定"
    notify = f"<#{st.get('notify_channel_id')}>" if st.get("notify_channel_id") else "未設定"
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "(なし)"

    e = discord.Embed(title="🧩 枠作成ウィザード", color=0x5865F2)
    e.add_field(name="日付", value=day, inline=False)
    e.add_field(name="開始", value=start, inline=True)
    e.add_field(name="終了", value=end, inline=True)
    e.add_field(name="間隔", value=interval, inline=False)
    e.add_field(name="通知チャンネル", value=notify, inline=False)
    e.add_field(name="@everyone", value=everyone, inline=True)
    e.add_field(name="タイトル", value=title, inline=False)
    e.set_footer(text="全部選んだら「作成」を押してね👇")
    return e


class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)
        self.st = st

        # ---- Row 0: day buttons + everyone toggle
        self.add_item(discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today", row=0))
        self.add_item(discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow", row=0))
        self.add_item(discord.ui.Button(label="@everyone切替", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle", row=0))

        # ---- Row 1: start hour/min
        self.add_item(_HourSelect(custom_id="setup:start_hour", placeholder="開始(時)", row=1))
        self.add_item(_MinSelect(custom_id="setup:start_min", placeholder="開始(分)", row=1))

        # ---- Row 2: end hour/min
        self.add_item(_HourSelect(custom_id="setup:end_hour", placeholder="終了(時)", row=2))
        self.add_item(_MinSelect(custom_id="setup:end_min", placeholder="終了(分)", row=2))

        # ---- Row 3: interval + notify channel
        self.add_item(_IntervalSelect(custom_id="setup:interval", placeholder="間隔(分)", row=3))
        self.add_item(discord.ui.ChannelSelect(
            custom_id="setup:notify_channel",
            placeholder="通知チャンネル",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=3
        ))

        # ---- Row 4: CREATE  ←★これが無いと「作成」出ない
        self.add_item(discord.ui.Button(label="作成", style=discord.ButtonStyle.success, custom_id="setup:create", row=4))


class _HourSelect(discord.ui.Select):
    def __init__(self, *, custom_id: str, placeholder: str, row: int):
        options = [discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}") for h in range(24)]
        super().__init__(custom_id=custom_id, placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)


class _MinSelect(discord.ui.Select):
    def __init__(self, *, custom_id: str, placeholder: str, row: int):
        mins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        options = [discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}") for m in mins]
        super().__init__(custom_id=custom_id, placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)


class _IntervalSelect(discord.ui.Select):
    def __init__(self, *, custom_id: str, placeholder: str, row: int):
        values = [5, 10, 15, 20, 30, 60]
        options = [discord.SelectOption(label=f"{v}分", value=str(v)) for v in values]
        super().__init__(custom_id=custom_id, placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)


def build_setup_view(st: dict) -> discord.ui.View:
    return SetupWizardView(st)