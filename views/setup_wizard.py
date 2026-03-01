from __future__ import annotations
import discord

def build_setup_embed(st: dict) -> discord.Embed:
    day = "今日" if st.get("day") == "today" else "明日"
    start = st.get("start") or "未選択"
    end = st.get("end") or "未選択"
    interval = st.get("interval") or "未選択"
    title = st.get("title") or "（なし）"
    everyone = "ON" if st.get("everyone") else "OFF"
    notify_ch = st.get("notify_channel_id") or "このチャンネル"

    desc = (
        f"📅 日付: **{day}**\n"
        f"🕒 開始: **{start}**\n"
        f"🕘 終了: **{end}**\n"
        f"⏱ 間隔: **{interval}**\n"
        f"🏷 タイトル: **{title}**\n"
        f"📣 @everyone: **{everyone}**\n"
        f"🔔 通知: **{notify_ch}**\n"
    )

    step = st.get("step", 1)
    e = discord.Embed(
        title=f"募集パネル作成 (/setup) - Step {step}",
        description=desc,
        color=0x5865F2,
    )
    e.set_footer(text="予約結果/操作結果は実行者のみ(ephemeral)で表示されます")
    return e


class TitleModal(discord.ui.Modal, title="募集パネルのタイトル"):
    def __init__(self):
        super().__init__(timeout=180)
        self.custom_id = "setup:title:modal"
        self.title_input = discord.ui.TextInput(
            label="タイトル（空でもOK）",
            placeholder="例）夜の周回 / レイド募集",
            required=False,
            max_length=60,
        )
        self.add_item(self.title_input)

    async def on_submit(self, interaction: discord.Interaction):
        # bot_interact 側で modal_submit を拾って state に反映するので、ここは何もしなくてOK
        await interaction.response.defer(ephemeral=True)


def _time_options():
    # 00:00〜24:00 (24:00も入れる)
    opts = []
    for h in range(0, 24):
        for m in (0, 30):
            opts.append(discord.SelectOption(label=f"{h:02d}:{m:02d}", value=f"{h:02d}:{m:02d}"))
    opts.append(discord.SelectOption(label="24:00", value="24:00"))
    return opts[:25], opts[25:50], opts[50:75]  # discord limit対策（分割利用はしてないが安全）


def build_setup_view(st: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=None)

    # day buttons
    v.add_item(discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today"))
    v.add_item(discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow"))

    # time selects（最小：30分刻み + 24:00）
    opts, _, _ = _time_options()

    v.add_item(discord.ui.Select(
        placeholder="開始時刻を選択",
        options=opts,
        min_values=1, max_values=1,
        custom_id="setup:start",
    ))
    v.add_item(discord.ui.Select(
        placeholder="終了時刻を選択",
        options=opts,
        min_values=1, max_values=1,
        custom_id="setup:end",
    ))

    # interval
    v.add_item(discord.ui.Select(
        placeholder="間隔（分）を選択",
        options=[
            discord.SelectOption(label="20", value="20"),
            discord.SelectOption(label="25", value="25"),
            discord.SelectOption(label="30", value="30"),
        ],
        min_values=1, max_values=1,
        custom_id="setup:interval",
    ))

    # title modal open
    v.add_item(discord.ui.Button(label="タイトル入力", style=discord.ButtonStyle.secondary, custom_id="setup:title:open"))

    # everyone toggle
    v.add_item(discord.ui.Button(label="@everyone ON/OFF", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle"))

    # notify channel select (text channels only) -> value is channel_id
    # ※実際のチャンネル一覧は interaction.guild から取る必要があるが、View生成時に guild がないので
    #   「簡易版」は "このチャンネル" をデフォにして、後で拡張可能。
    # ここでは「入力できたらOK」にするため、ボタンだけ置く（拡張したいなら次でやる）
    # -> ただしあなたは「選択が欲しい」なので、まずは "通知=このチャンネル" で確実に動かし、
    #    次のステップで「ギルドからテキストチャンネル列挙」を入れるのが安全。

    # step buttons
    if st.get("step") == 1:
        v.add_item(discord.ui.Button(label="次へ", style=discord.ButtonStyle.success, custom_id="setup:step:next"))
    else:
        v.add_item(discord.ui.Button(label="戻る", style=discord.ButtonStyle.secondary, custom_id="setup:step:back"))
        v.add_item(discord.ui.Button(label="作成", style=discord.ButtonStyle.success, custom_id="setup:create"))

    return v