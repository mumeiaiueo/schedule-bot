from __future__ import annotations
import discord


def build_setup_embed(st: dict) -> discord.Embed:
    day = "今日" if st.get("day") == "today" else "明日" if st.get("day") == "tomorrow" else "今日"
    start = st.get("start") or "--:--"
    end = st.get("end") or "--:--"
    interval = f"{st.get('interval')}分" if st.get("interval") else "未設定"
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "（未設定）"
    step = st.get("step", 1)

    e = discord.Embed(title=f"🧩 枠作成ウィザード（{step}/2）", color=0x5865F2)
    e.add_field(name="日付", value=day, inline=False)
    e.add_field(name="開始", value=start, inline=True)
    e.add_field(name="終了", value=end, inline=True)
    e.add_field(name="間隔", value=interval, inline=False)
    e.add_field(name="タイトル", value=title, inline=False)
    e.add_field(name="@everyone", value=everyone, inline=True)
    e.set_footer(text="1/2: 時刻を選ぶ → 次へ　｜　2/2: 間隔/タイトル/@everyone → 作成")
    return e


def _ph(base: str, val: str | None) -> str:
    return f"{base} [{val}]" if val else base


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
        values = [20, 25, 30]
        options = [discord.SelectOption(label=f"{v}分", value=str(v)) for v in values]
        super().__init__(custom_id=custom_id, placeholder=placeholder, options=options, min_values=1, max_values=1, row=row)


class SetupWizardViewStep1(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)

        # ✅ デフォルトは今日。選ばれてる方を primary に見せる
        day = st.get("day") or "today"
        today_style = discord.ButtonStyle.primary if day == "today" else discord.ButtonStyle.secondary
        tom_style = discord.ButtonStyle.primary if day == "tomorrow" else discord.ButtonStyle.secondary

        self.add_item(discord.ui.Button(label="今日", style=today_style, custom_id="setup:day:today", row=0))
        self.add_item(discord.ui.Button(label="明日", style=tom_style, custom_id="setup:day:tomorrow", row=0))

        # @everyone ON/OFF は色で分かる
        ev_style = discord.ButtonStyle.success if st.get("everyone") else discord.ButtonStyle.secondary
        ev_label = "📣 @everyone ON" if st.get("everyone") else "🔕 @everyone OFF"
        self.add_item(discord.ui.Button(label=ev_label, style=ev_style, custom_id="setup:everyone:toggle", row=0))

        self.add_item(discord.ui.Button(label="次へ", style=discord.ButtonStyle.success, custom_id="setup:step:next", row=0))

        self.add_item(_HourSelect(custom_id="setup:start_hour", placeholder=_ph("開始(時)", st.get("start_hour")), row=1))
        self.add_item(_MinSelect(custom_id="setup:start_min", placeholder=_ph("開始(分) 5分刻み", st.get("start_min")), row=2))
        self.add_item(_HourSelect(custom_id="setup:end_hour", placeholder=_ph("終了(時)", st.get("end_hour")), row=3))
        self.add_item(_MinSelect(custom_id="setup:end_min", placeholder=_ph("終了(分) 5分刻み", st.get("end_min")), row=4))


class SetupWizardViewStep2(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)

        self.add_item(discord.ui.Button(label="戻る", style=discord.ButtonStyle.secondary, custom_id="setup:step:back", row=0))

        # タイトル入力（モーダル）
        self.add_item(discord.ui.Button(label="✏️ タイトル", style=discord.ButtonStyle.primary, custom_id="setup:title:open", row=0))

        # @everyone ON/OFF は色で分かる
        ev_style = discord.ButtonStyle.success if st.get("everyone") else discord.ButtonStyle.secondary
        ev_label = "📣 @everyone ON" if st.get("everyone") else "🔕 @everyone OFF"
        self.add_item(discord.ui.Button(label=ev_label, style=ev_style, custom_id="setup:everyone:toggle", row=0))

        self.add_item(discord.ui.Button(label="作成", style=discord.ButtonStyle.success, custom_id="setup:create", row=0))

        self.add_item(_IntervalSelect(
            custom_id="setup:interval",
            placeholder=_ph("間隔(分)", str(st.get("interval")) if st.get("interval") else None),
            row=1
        ))


def build_setup_view(st: dict) -> discord.ui.View:
    step = st.get("step", 1)
    if step == 2:
        return SetupWizardViewStep2(st)
    return SetupWizardViewStep1(st)