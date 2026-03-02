import discord
from utils.time_utils import hour_options, minute_options

def _btn(label, custom_id, style, row):
    return discord.ui.Button(label=label, custom_id=custom_id, style=style, row=row)

def _sel(custom_id: str, placeholder: str, options, row: int):
    return discord.ui.Select(
        custom_id=custom_id,
        placeholder=placeholder,
        min_values=1,
        max_values=1,
        options=options,
        row=row
    )

def _hour_select(custom_id: str, placeholder: str, row: int):
    opts = [discord.SelectOption(label=h, value=h) for h in hour_options()]  # 24件
    return _sel(custom_id, placeholder, opts, row)

def _min_select(custom_id: str, placeholder: str, row: int):
    opts = [discord.SelectOption(label=m, value=m) for m in minute_options(5)]  # 12件
    return _sel(custom_id, placeholder, opts, row)

def _interval_select(custom_id: str, placeholder: str, row: int):
    options = [
        discord.SelectOption(label="20分", value="20"),
        discord.SelectOption(label="25分", value="25"),
        discord.SelectOption(label="30分", value="30"),
    ]
    return _sel(custom_id, placeholder, options, row)

class TitleModal(discord.ui.Modal, title="募集タイトル入力"):
    title_input = discord.ui.TextInput(
        label="タイトル",
        placeholder="例：配信枠 / 作業枠 / なんでも",
        required=False,
        max_length=80
    )

    def __init__(self, st: dict):
        super().__init__(timeout=300)
        self.st = st

    async def on_submit(self, interaction: discord.Interaction):
        self.st["title"] = (self.title_input.value or "").strip()
        await interaction.response.send_message("✅ タイトルを保存しました", ephemeral=True)

class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)
        step = int(st.get("step", 1))
        day = st.get("day", "today")

        if step == 1:
            # Row0: day buttons + next（←ここがポイント）
            self.add_item(_btn("今日", "setup:day:today",
                               discord.ButtonStyle.primary if day == "today" else discord.ButtonStyle.secondary, row=0))
            self.add_item(_btn("明日", "setup:day:tomorrow",
                               discord.ButtonStyle.primary if day == "tomorrow" else discord.ButtonStyle.secondary, row=0))
            self.add_item(_btn("次へ", "setup:step:2", discord.ButtonStyle.success, row=0))

            # Row1-2: start time
            self.add_item(_hour_select("setup:start_hour", "開始(時) 例:19", row=1))
            self.add_item(_min_select("setup:start_min", "開始(分) 例:00", row=2))

            # Row3-4: end time
            self.add_item(_hour_select("setup:end_hour", "終了(時) 例:21", row=3))
            self.add_item(_min_select("setup:end_min", "終了(分) 例:00", row=4))

        else:
            # Row0: interval
            self.add_item(_interval_select("setup:interval", "間隔（20/25/30）", row=0))

            # Row1: title + everyone
            self.add_item(_btn("📝 タイトル入力", "setup:title:open", discord.ButtonStyle.secondary, row=1))
            everyone = bool(st.get("everyone", False))
            self.add_item(_btn("@everyone ON" if everyone else "@everyone OFF",
                               "setup:everyone:toggle",
                               discord.ButtonStyle.danger if everyone else discord.ButtonStyle.secondary,
                               row=1))

            # Row2: notify channel select
            cs = discord.ui.ChannelSelect(
                custom_id="setup:notify_channel",
                placeholder="通知チャンネル（未選択=このチャンネル）",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text],
                row=2,
            )
            self.add_item(cs)

            # Row3: back + create
            self.add_item(_btn("戻る", "setup:step:1", discord.ButtonStyle.secondary, row=3))
            self.add_item(_btn("作成", "setup:create", discord.ButtonStyle.success, row=3))

def build_setup_view(st: dict) -> discord.ui.View:
    return SetupWizardView(st)

def build_setup_embed(st: dict) -> discord.Embed:
    step = int(st.get("step", 1))
    day = st.get("day", "today")
    start = st.get("start")
    end = st.get("end")
    interval = st.get("interval")
    title = st.get("title", "")
    everyone = bool(st.get("everyone", False))
    notify = st.get("notify_channel")

    e = discord.Embed(title="募集パネル作成ウィザード", color=0x5865F2)
    e.add_field(name="Step", value=str(step), inline=True)
    e.add_field(name="日付", value=("今日" if day == "today" else "明日"), inline=True)
    e.add_field(name="開始", value=(start or "未選択"), inline=True)
    e.add_field(name="終了", value=(end or "未選択"), inline=True)

    if step == 2:
        e.add_field(name="間隔", value=(f"{interval}分" if interval else "未選択"), inline=True)
        e.add_field(name="タイトル", value=(title if title else "（なし）"), inline=False)
        e.add_field(name="@everyone", value=("ON" if everyone else "OFF"), inline=True)
        e.add_field(name="通知チャンネル", value=(f"<#{notify}>" if notify else "このチャンネル"), inline=False)

    e.set_footer(text="ボタン/セレクトで設定して「作成」")
    return e