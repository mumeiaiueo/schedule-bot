from __future__ import annotations

import discord


# =============================
# UI: Setup Wizard
# =============================

def _val_or_dash(v):
    return v if v not in (None, "", "None") else "—"


def build_setup_embed(st: dict) -> discord.Embed:
    step = int(st.get("step") or 1)
    day = st.get("day")
    start = st.get("start")
    end = st.get("end")
    interval = st.get("interval")
    notify_channel_id = st.get("notify_channel_id")
    everyone = bool(st.get("everyone"))
    title = st.get("title")

    e = discord.Embed(
        title="🧩 募集パネル作成ウィザード",
        description="下のボタン/セレクトで設定して、最後に **作成** を押してね。",
        color=0x5865F2,
    )

    e.add_field(
        name="Step",
        value=f"**{step}/2**",
        inline=True,
    )
    e.add_field(
        name="日付",
        value=f"**{_val_or_dash(day)}**（today / tomorrow）",
        inline=True,
    )
    e.add_field(
        name="時間",
        value=f"**{_val_or_dash(start)} ~ {_val_or_dash(end)}**",
        inline=True,
    )

    e.add_field(
        name="間隔（分）",
        value=f"**{_val_or_dash(interval)}**",
        inline=True,
    )

    e.add_field(
        name="@everyone",
        value="**ON**（作成時に1回だけ送信）" if everyone else "**OFF**",
        inline=True,
    )

    if notify_channel_id:
        e.add_field(
            name="通知チャンネル（3分前）",
            value=f"<#{notify_channel_id}>",
            inline=False,
        )
    else:
        e.add_field(
            name="通知チャンネル（3分前）",
            value="（未選択なら、このチャンネルに通知）",
            inline=False,
        )

    e.add_field(
        name="タイトル",
        value=_val_or_dash(title),
        inline=False,
    )

    if step == 1:
        e.set_footer(text="Step1: 日付/開始/終了 を決めて「次へ」")
    else:
        e.set_footer(text="Step2: 間隔/タイトル/@everyone/通知チャンネル を決めて「作成」")

    return e


# -----------------------------
# “何もしない” callback（処理は bot_interact.py 側）
# -----------------------------
async def _noop_callback(interaction: discord.Interaction):
    return


def _make_button(*, label: str, custom_id: str, style: discord.ButtonStyle, disabled: bool = False, emoji=None):
    b = discord.ui.Button(label=label, custom_id=custom_id, style=style, disabled=disabled, emoji=emoji)
    b.callback = _noop_callback
    return b


def _make_select(*, custom_id: str, placeholder: str, options: list[discord.SelectOption], disabled: bool = False):
    s = discord.ui.Select(custom_id=custom_id, placeholder=placeholder, min_values=1, max_values=1, options=options, disabled=disabled)
    s.callback = _noop_callback
    return s


def _make_channel_select(*, custom_id: str, placeholder: str):
    # discord.py 2.4+: ChannelSelect が使える
    cs = discord.ui.ChannelSelect(
        custom_id=custom_id,
        placeholder=placeholder,
        min_values=1,
        max_values=1,
        channel_types=[discord.ChannelType.text],
    )
    cs.callback = _noop_callback
    return cs


def _hour_options():
    return [discord.SelectOption(label=f"{h:02d}", value=str(h)) for h in range(0, 25)]  # 0..24 (24:00対応)


def _min_options():
    # 00/05/10/15/20/25/30/35/40/45/50/55
    mins = list(range(0, 60, 5))
    return [discord.SelectOption(label=f"{m:02d}", value=str(m)) for m in mins]


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

        # --- Step共通：日付ボタン ---
        day = st.get("day")
        today_style = discord.ButtonStyle.primary if day == "today" else discord.ButtonStyle.secondary
        tom_style = discord.ButtonStyle.primary if day == "tomorrow" else discord.ButtonStyle.secondary

        self.add_item(_make_button(label="今日", custom_id="setup:day:today", style=today_style))
        self.add_item(_make_button(label="明日", custom_id="setup:day:tomorrow", style=tom_style))

        # --- Step1：開始/終了選択 ---
        if step == 1:
            sh = st.get("start_hour")
            sm = st.get("start_min")
            eh = st.get("end_hour")
            em = st.get("end_min")

            self.add_item(_make_select(
                custom_id="setup:start_hour",
                placeholder=f"開始(時) 現在: {_val_or_dash(sh)}",
                options=_hour_options(),
            ))
            self.add_item(_make_select(
                custom_id="setup:start_min",
                placeholder=f"開始(分) 現在: {_val_or_dash(sm)}",
                options=_min_options(),
            ))
            self.add_item(_make_select(
                custom_id="setup:end_hour",
                placeholder=f"終了(時) 現在: {_val_or_dash(eh)}",
                options=_hour_options(),
            ))
            self.add_item(_make_select(
                custom_id="setup:end_min",
                placeholder=f"終了(分) 現在: {_val_or_dash(em)}",
                options=_min_options(),
            ))

            # 次へ
            self.add_item(_make_button(label="次へ", custom_id="setup:step:next", style=discord.ButtonStyle.success))

        # --- Step2：間隔/タイトル/@everyone/通知チャンネル/作成 ---
        else:
            interval = st.get("interval")
            everyone = bool(st.get("everyone"))

            self.add_item(_make_select(
                custom_id="setup:interval",
                placeholder=f"間隔（分） 現在: {_val_or_dash(interval)}",
                options=_interval_options(),
            ))

            # タイトル入力（モーダルを開く想定：bot_interact.py 側で interaction.response.send_modal）
            self.add_item(_make_button(label="タイトル入力", custom_id="setup:title:open", style=discord.ButtonStyle.secondary, emoji="📝"))

            # everyone toggle
            ev_style = discord.ButtonStyle.danger if everyone else discord.ButtonStyle.secondary
            ev_label = "@everyone ON" if everyone else "@everyone OFF"
            self.add_item(_make_button(label=ev_label, custom_id="setup:everyone:toggle", style=ev_style))

            # 通知チャンネル（3分前）
            self.add_item(_make_channel_select(
                custom_id="setup:notify_channel",
                placeholder="通知チャンネル（3分前）を選択（未選択=このチャンネル）",
            ))

            # 戻る / 作成
            self.add_item(_make_button(label="戻る", custom_id="setup:step:back", style=discord.ButtonStyle.secondary))
            self.add_item(_make_button(label="作成", custom_id="setup:create", style=discord.ButtonStyle.success))


def build_setup_view(st: dict) -> discord.ui.View:
    return SetupWizardView(st)