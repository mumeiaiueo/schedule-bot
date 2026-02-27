# views/setup_wizard.py
import discord


def _hour_options():
    return [discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}") for h in range(0, 24)]


def _min_options():
    # 5分刻み
    mins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    return [discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}") for m in mins]


def build_setup_embed(st: dict) -> discord.Embed:
    day = st.get("day")
    day_text = "未選択" if not day else ("今日" if day == "today" else "明日")

    start = "未設定"
    if st.get("start_h") and st.get("start_m"):
        start = f"{st['start_h']}:{st['start_m']}"

    end = "未設定"
    if st.get("end_h") and st.get("end_m"):
        end = f"{st['end_h']}:{st['end_m']}"

    interval = st.get("interval")
    interval_text = "未選択" if not interval else f"{interval} 分"

    notify = st.get("notify_channel_id")
    notify_text = "未設定" if not notify else f"<#{notify}>"

    everyone = "ON" if st.get("everyone") else "OFF"

    e = discord.Embed(title="🧩 枠作成ウィザード", description="ボタン/セレクトで順に埋めてね")
    e.add_field(name="📅 日付（必須）", value=day_text, inline=True)
    e.add_field(name="⏱ 開始（必須）", value=start, inline=True)
    e.add_field(name="⏱ 終了（必須）", value=end, inline=True)
    e.add_field(name="🔁 間隔（必須）", value=interval_text, inline=True)
    e.add_field(name="🔔 通知チャンネル（必須）", value=notify_text, inline=False)
    e.add_field(name="📣 everyone（任意）", value=everyone, inline=True)
    e.set_footer(text="※ 終了が開始より早い場合は、日跨ぎ扱いで作成します")
    return e


class _StartHour(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="setup:start_h",
            placeholder="開始(時)",
            min_values=1,
            max_values=1,
            options=_hour_options(),
        )


class _StartMin(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="setup:start_m",
            placeholder="開始(分) 5分刻み",
            min_values=1,
            max_values=1,
            options=_min_options(),
        )


class _EndHour(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="setup:end_h",
            placeholder="終了(時)",
            min_values=1,
            max_values=1,
            options=_hour_options(),
        )


class _EndMin(discord.ui.Select):
    def __init__(self):
        super().__init__(
            custom_id="setup:end_m",
            placeholder="終了(分) 5分刻み",
            min_values=1,
            max_values=1,
            options=_min_options(),
        )


class _NotifyChannel(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            custom_id="setup:notify_ch",
            placeholder="通知チャンネルを選択（必須）",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )


class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)

        # row0: 今日/明日
        self.add_item(discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today", row=0))
        self.add_item(discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow", row=0))

        # row1-2: 時刻
        self.add_item(_StartHour())
        self.add_item(_StartMin())
        self.add_item(_EndHour())
        self.add_item(_EndMin())

        # row3: 間隔
        self.add_item(discord.ui.Button(label="20分", style=discord.ButtonStyle.success, custom_id="setup:interval:20", row=3))
        self.add_item(discord.ui.Button(label="25分", style=discord.ButtonStyle.success, custom_id="setup:interval:25", row=3))
        self.add_item(discord.ui.Button(label="30分", style=discord.ButtonStyle.success, custom_id="setup:interval:30", row=3))

        # row4: 通知チャンネル
        self.add_item(_NotifyChannel())

        # row5: everyone / 作成 / キャンセル
        self.add_item(discord.ui.Button(label="everyone 切替", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle", row=5))
        self.add_item(discord.ui.Button(label="✅ 作成", style=discord.ButtonStyle.primary, custom_id="setup:create", row=5))
        self.add_item(discord.ui.Button(label="✖ キャンセル", style=discord.ButtonStyle.danger, custom_id="setup:cancel", row=5))


def build_setup_view(st: dict) -> discord.ui.View:
    # 今回は state による disabled 制御はしない（安定優先）
    return SetupView()