# views/setup_wizard.py
import discord

# 5分刻み
MIN_OPTIONS = [f"{m:02d}" for m in range(0, 60, 5)]
HOUR_OPTIONS = [f"{h:02d}" for h in range(0, 24)]


def build_setup_embed(st: dict) -> discord.Embed:
    def t(v, fallback="未設定"):
        return v if v else fallback

    day = "今日" if st.get("day") == "today" else ("明日" if st.get("day") == "tomorrow" else "未設定")
    start = f"{t(st.get('start_hour'),'--')}:{t(st.get('start_min'),'--')}"
    end = f"{t(st.get('end_hour'),'--')}:{t(st.get('end_min'),'--')}"
    interval = st.get("interval")
    notify = st.get("notify_channel_id")
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "(なし)"

    desc = (
        f"**日付**：{day}\n"
        f"**開始**：{start}\n"
        f"**終了**：{end}\n"
        f"**間隔**：{interval if interval else '未設定'}\n"
        f"**通知チャンネル**：{f'<#{notify}>' if notify else '未設定'}\n"
        f"**@everyone**：{everyone}\n"
        f"**タイトル**：{title}\n\n"
        "全部選んだら **作成** を押してね👇"
    )
    return discord.Embed(title="🧩 枠作成ウィザード", description=desc, color=0x5865F2)


class TitleModal(discord.ui.Modal, title="タイトル入力（任意）"):
    text = discord.ui.TextInput(label="タイトル", required=False, max_length=50, placeholder="例：夜の募集")

    def __init__(self, st: dict):
        super().__init__()
        self.st = st

    async def on_submit(self, interaction: discord.Interaction):
        v = str(self.text.value).strip()
        self.st["title"] = v if v else None
        await interaction.response.defer(ephemeral=True)


def build_setup_view(st: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=600)

    # 0) 今日/明日
    b_today = discord.ui.Button(label="今日", style=discord.ButtonStyle.primary if st.get("day") == "today" else discord.ButtonStyle.secondary, custom_id="setup:day:today", row=0)
    b_tomo  = discord.ui.Button(label="明日", style=discord.ButtonStyle.primary if st.get("day") == "tomorrow" else discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow", row=0)
    v.add_item(b_today); v.add_item(b_tomo)

    # 1) 開始（時/分）
    sel_sh = discord.ui.Select(
        placeholder="開始：時", min_values=1, max_values=1,
        options=[discord.SelectOption(label=h, value=h, default=(st.get("start_hour")==h)) for h in HOUR_OPTIONS],
        custom_id="setup:start_hour", row=1
    )
    sel_sm = discord.ui.Select(
        placeholder="開始：分(5分刻み)", min_values=1, max_values=1,
        options=[discord.SelectOption(label=m, value=m, default=(st.get("start_min")==m)) for m in MIN_OPTIONS],
        custom_id="setup:start_min", row=1
    )
    v.add_item(sel_sh); v.add_item(sel_sm)

    # 2) 終了（時/分）
    sel_eh = discord.ui.Select(
        placeholder="終了：時", min_values=1, max_values=1,
        options=[discord.SelectOption(label=h, value=h, default=(st.get("end_hour")==h)) for h in HOUR_OPTIONS],
        custom_id="setup:end_hour", row=2
    )
    sel_em = discord.ui.Select(
        placeholder="終了：分(5分刻み)", min_values=1, max_values=1,
        options=[discord.SelectOption(label=m, value=m, default=(st.get("end_min")==m)) for m in MIN_OPTIONS],
        custom_id="setup:end_min", row=2
    )
    v.add_item(sel_eh); v.add_item(sel_em)

    # 3) 間隔 20/25/30
    for mins in (20, 25, 30):
        v.add_item(discord.ui.Button(
            label=f"{mins}分",
            style=discord.ButtonStyle.success if st.get("interval")==mins else discord.ButtonStyle.secondary,
            custom_id=f"setup:interval:{mins}",
            row=3
        ))

    # 4) 通知チャンネル（必須）+ everyone + タイトル + 作成
    # チャンネルは ChannelSelect を使う
    ch_sel = discord.ui.ChannelSelect(
        channel_types=[discord.ChannelType.text],
        placeholder="3分前通知チャンネル（必須）",
        min_values=1, max_values=1,
        custom_id="setup:notify_channel",
        row=4
    )
    v.add_item(ch_sel)

    b_every = discord.ui.Button(
        label="@everyone " + ("ON" if st.get("everyone") else "OFF"),
        style=discord.ButtonStyle.danger if st.get("everyone") else discord.ButtonStyle.secondary,
        custom_id="setup:everyone:toggle",
        row=4
    )
    v.add_item(b_every)

    # タイトル入力ボタン（Modal）
    b_title = discord.ui.Button(label="タイトル入力", style=discord.ButtonStyle.secondary, custom_id="setup:title:open", row=4)
    b_clear = discord.ui.Button(label="タイトル消す", style=discord.ButtonStyle.secondary, custom_id="setup:title:clear", row=4)
    b_create = discord.ui.Button(label="作成", style=discord.ButtonStyle.primary, custom_id="setup:create", row=4)

    async def title_cb(interaction: discord.Interaction):
        await interaction.response.send_modal(TitleModal(st))

    b_title.callback = title_cb

    v.add_item(b_title)
    v.add_item(b_clear)
    v.add_item(b_create)

    return v