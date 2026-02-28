# views/setup_wizard.py
from __future__ import annotations

import discord


def build_setup_embed(st: dict) -> discord.Embed:
    day = "今日" if st.get("day") == "today" else "明日" if st.get("day") == "tomorrow" else "未設定"

    sh = st.get("start_hour")
    sm = st.get("start_min")
    eh = st.get("end_hour")
    em = st.get("end_min")

    start = f"{sh}:{sm}" if (sh is not None and sm is not None) else "--:--"
    end = f"{eh}:{em}" if (eh is not None and em is not None) else "--:--"

    interval = f"{st.get('interval')}分" if st.get("interval") else "未設定"
    notify = f"<#{st.get('notify_channel_id')}>" if st.get("notify_channel_id") else "未設定"
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "(なし)"
    step = st.get("_step", 1)

    e = discord.Embed(title="🧩 枠作成ウィザード", color=0x5865F2)
    e.add_field(name="ステップ", value=f"{step}/3", inline=False)
    e.add_field(name="日付", value=day, inline=False)
    e.add_field(name="開始", value=start, inline=True)
    e.add_field(name="終了", value=end, inline=True)
    e.add_field(name="間隔", value=interval, inline=False)
    e.add_field(name="通知チャンネル", value=notify, inline=False)
    e.add_field(name="@everyone", value=everyone, inline=True)
    e.add_field(name="タイトル", value=title, inline=False)
    e.set_footer(text="選択して進めてね👇（1行にSelect1個＝落ちない）")
    return e


# ------------------------------
# Selects
# ------------------------------
class HourSelect(discord.ui.Select):
    def __init__(self, placeholder: str):
        options = [discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}") for h in range(24)]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, row=1)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        if v.step == 1:
            v.st["start_hour"] = self.values[0]
        elif v.step == 2:
            v.st["end_hour"] = self.values[0]
        await v.refresh(interaction)


class MinSelect(discord.ui.Select):
    def __init__(self, placeholder: str, row: int):
        mins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
        options = [discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}") for m in mins]
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        if v.step == 1:
            v.st["start_min"] = self.values[0]
        elif v.step == 2:
            v.st["end_min"] = self.values[0]
        await v.refresh(interaction)


class IntervalSelect(discord.ui.Select):
    def __init__(self):
        values = [5, 10, 15, 20, 30, 60]
        options = [discord.SelectOption(label=f"{v}分", value=str(v)) for v in values]
        super().__init__(placeholder="間隔(分)", options=options, min_values=1, max_values=1, row=3)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        v.st["interval"] = int(self.values[0])
        await v.refresh(interaction)


class NotifyChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="通知チャンネル",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        ch = self.values[0]
        v.st["notify_channel_id"] = ch.id
        await v.refresh(interaction)


# ------------------------------
# View (3-step)
# ------------------------------
class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)
        self.st = st
        self.step = int(st.get("_step", 1))
        self.render()

    def render(self):
        # items 全消しして作り直す（Row設計を固定して落ちない）
        self.clear_items()

        # ---- Row0: always buttons (最大5個までOK)
        if self.step == 1:
            self.add_item(DayTodayButton())
            self.add_item(DayTomorrowButton())
            self.add_item(EveryoneToggleButton())
            self.add_item(NextButton())
        elif self.step == 2:
            self.add_item(BackButton())
            self.add_item(EveryoneToggleButton())
            self.add_item(NextButton())
        elif self.step == 3:
            self.add_item(BackButton())
            self.add_item(EveryoneToggleButton())
            self.add_item(CreateButton())
            self.add_item(CancelButton())

        # ---- Step contents (Selectは「1行に1個」)
        if self.step == 1:
            # Row1: HourSelect / Row2: MinSelect
            self.add_item(HourSelect("開始(時)"))
            self.add_item(MinSelect("開始(分)", row=2))

        elif self.step == 2:
            # Row1: HourSelect / Row2: MinSelect / Row3: IntervalSelect
            self.add_item(HourSelect("終了(時)"))
            self.add_item(MinSelect("終了(分)", row=2))
            self.add_item(IntervalSelect())

        elif self.step == 3:
            # Row1: ChannelSelect only（幅5なので同じrowにボタン置かない）
            self.add_item(NotifyChannelSelect())

    async def refresh(self, interaction: discord.Interaction):
        self.st["_step"] = self.step
        embed = build_setup_embed(self.st)
        self.render()
        await interaction.response.edit_message(embed=embed, view=self)

    def _can_next_1(self) -> bool:
        return (
            self.st.get("day") in ("today", "tomorrow")
            and self.st.get("start_hour") is not None
            and self.st.get("start_min") is not None
        )

    def _can_next_2(self) -> bool:
        return (
            self.st.get("end_hour") is not None
            and self.st.get("end_min") is not None
            and self.st.get("interval") is not None
        )

    def _can_create(self) -> bool:
        return (
            self._can_next_1()
            and self._can_next_2()
            and self.st.get("notify_channel_id") is not None
        )


# ------------------------------
# Buttons
# ------------------------------
class DayTodayButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="今日", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        v.st["day"] = "today"
        await v.refresh(interaction)


class DayTomorrowButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="明日", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        v.st["day"] = "tomorrow"
        await v.refresh(interaction)


class EveryoneToggleButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="@everyone切替", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        v.st["everyone"] = not bool(v.st.get("everyone"))
        await v.refresh(interaction)


class NextButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="次へ ▶", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore

        if v.step == 1 and not v._can_next_1():
            await interaction.response.send_message("❌ 日付・開始(時/分)を選んでね", ephemeral=True)
            return

        if v.step == 2 and not v._can_next_2():
            await interaction.response.send_message("❌ 終了(時/分)と間隔を選んでね", ephemeral=True)
            return

        v.step = min(3, v.step + 1)
        await v.refresh(interaction)


class BackButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="◀ 戻る", style=discord.ButtonStyle.secondary, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        v.step = max(1, v.step - 1)
        await v.refresh(interaction)


class CancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="キャンセル", style=discord.ButtonStyle.danger, row=0)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(content="キャンセルしました", embed=None, view=None)


class CreateButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="作成", style=discord.ButtonStyle.success, row=0)

    async def callback(self, interaction: discord.Interaction):
        v: SetupWizardView = self.view  # type: ignore
        if not v._can_create():
            await interaction.response.send_message("❌ まだ未設定があります（通知チャンネルまで選んでね）", ephemeral=True)
            return

        # ここでは「作成」ボタンが押せる状態まで保証するだけ。
        # 実際のDB作成処理はあなたの bot_interact / DataManager 側で
        # custom_id ではなく、ここから呼ぶ形にするのが一番安定。
        await interaction.response.send_message("✅ 作成処理を実行してね（ここに作成処理を接続）", ephemeral=True)


def build_setup_view(st: dict) -> discord.ui.View:
    return SetupWizardView(st)