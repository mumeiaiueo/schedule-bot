from __future__ import annotations
import discord


def _val_or_dash(v):
    return v if v not in (None, "", "None") else "—"


def build_setup_embed(st: dict) -> discord.Embed:
    step = int(st.get("step") or 1)

    day = st.get("day") or "today"
    start = st.get("start") or "—"
    end = st.get("end") or "—"
    interval = st.get("interval")
    notify_channel_id = st.get("notify_channel_id")
    everyone = bool(st.get("everyone"))
    title = st.get("title")

    e = discord.Embed(
        title="🧩 募集パネル作成ウィザード",
        description="下のボタン/セレクトで設定して、最後に **作成** を押してね。",
        color=0x5865F2,
    )

    e.add_field(name="Step", value=f"**{step}/2**", inline=True)
    e.add_field(name="日付", value=("**今日**" if day == "today" else "**明日**"), inline=True)
    e.add_field(name="時間", value=f"**{start} ~ {end}**", inline=True)

    e.add_field(name="間隔（分）", value=f"**{_val_or_dash(interval)}**", inline=True)
    e.add_field(name="@everyone", value=("**ON（作成時に1回）**" if everyone else "**OFF**"), inline=True)

    if notify_channel_id:
        e.add_field(name="通知チャンネル（3分前）", value=f"<#{notify_channel_id}>", inline=False)
    else:
        e.add_field(name="通知チャンネル（3分前）", value="（未選択なら、このチャンネルに通知）", inline=False)

    e.add_field(name="タイトル", value=_val_or_dash(title), inline=False)

    e.set_footer(text=("Step1: 日付/開始/終了 → 次へ" if step == 1 else "Step2: 間隔/タイトル/@everyone/通知 → 作成"))
    return e


async def _noop(interaction: discord.Interaction):
    return


def _btn(label: str, custom_id: str, style: discord.ButtonStyle, row: int | None = None):
    b = discord.ui.Button(label=label, custom_id=custom_id, style=style, row=row)
    b.callback = _noop
    return b


def _sel(custom_id: str, placeholder: str, options: list[discord.SelectOption], row: int | None = None):
    s = discord.ui.Select(custom_id=custom_id, placeholder=placeholder, min_values=1, max_values=1, options=options, row=row)
    s.callback = _noop
    return s


def _hour_options():
    return [discord.SelectOption(label=f"{h:02d}", value=str(h)) for h in range(0, 25)]  # 0..24


def _min_options():
    return [discord.SelectOption(label=f"{m:02d}", value=str(m)) for m in range(0, 60, 5)]


def _interval_options():
    return [
        discord.SelectOption(label="20", value="20"),
        discord.SelectOption(label="25", value="25"),
        discord.SelectOption(label="30", value="30"),
    ]


class SetupWizardView(discord.ui.View):
    def __init__(self, st: dict):
        super().__init__(timeout=600)
        step = int(st.get("step") or 1)
        day = st.get("day") or "today"

        # 日付
        self.add_item(_btn("今日", "setup:day:today", discord.ButtonStyle.primary if day == "today" else discord.ButtonStyle.secondary, row=0))
        self.add_item(_btn("明日", "setup:day:tomorrow", discord.ButtonStyle.primary if day == "tomorrow" else discord.ButtonStyle.secondary, row=0))

        if step == 1:
            self.add_item(_sel("setup:start_hour", f"開始(時) 現在:{_val_or_dash(st.get('start_hour'))}", _hour_options(), row=1))
            self.add_item(_sel("setup:start_min", f"開始(分) 現在:{_val_or_dash(st.get('start_min'))}", _min_options(), row=2))
            self.add_item(_sel("setup:end_hour", f"終了(時) 現在:{_val_or_dash(st.get('end_hour'))}", _hour_options(), row=3))
            self.add_item(_sel("setup:end_min", f"終了(分) 現在:{_val_or_dash(st.get('end_min'))}", _min_options(), row=4))

            self.add_item(_btn("次へ", "setup:step:next", discord.ButtonStyle.success, row=0))

        else:
            self.add_item(_sel("setup:interval", f"間隔（分） 現在:{_val_or_dash(st.get('interval'))}", _interval_options(), row=1))

            # タイトル入力（モーダル）
            self.add_item(_btn("📝 タイトル入力", "setup:title:open", discord.ButtonStyle.secondary, row=0))

            everyone = bool(st.get("everyone"))
            ev_style = discord.ButtonStyle.danger if everyone else discord.ButtonStyle.secondary
            ev_label = "@everyone ON" if everyone else "@everyone OFF"
            self.add_item(_btn(ev_label, "setup:everyone:toggle", ev_style, row=0))

            # 通知チャンネル
            cs = discord.ui.ChannelSelect(
                custom_id="setup:notify_channel",
                placeholder="通知チャンネル（3分前）を選択（未選択=このチャンネル）",
                min_values=1,
                max_values=1,
                channel_types=[discord.ChannelType.text],
                row=2,
            )
            cs.callback = _noop
            self.add_item(cs)

            self.add_item(_btn("戻る", "setup:step:back", discord.ButtonStyle.secondary, row=0))
            self.add_item(_btn("作成", "setup:create", discord.ButtonStyle.success, row=0))


def build_setup_view(st: dict) -> discord.ui.View:
    return SetupWizardView(st)


class TitleModal(discord.ui.Modal, title="募集タイトル"):
    def __init__(self):
        super().__init__(custom_id="setup:title:modal")

        self.title_input = discord.ui.TextInput(
            label="タイトル（空でもOK）",
            placeholder="例：夜の部 / VC参加者募集 など",
            required=False,
            max_length=60,
        )
        self.add_item(self.title_input)