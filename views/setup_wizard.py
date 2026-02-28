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


def build_setup_view(st):
    v = discord.ui.View(timeout=300)

    # --- 1行目 ---
    btn_today = discord.ui.Button(
        label="今日",
        custom_id="setup:day:today",
        style=discord.ButtonStyle.primary,
        row=0
    )
    btn_tomorrow = discord.ui.Button(
        label="明日",
        custom_id="setup:day:tomorrow",
        style=discord.ButtonStyle.secondary,
        row=0
    )
    v.add_item(btn_today)
    v.add_item(btn_tomorrow)

    # --- 2行目 ---
    sel_sh = discord.ui.Select(
        placeholder="開始 時",
        custom_id="setup:start_hour",
        options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(24)],
        row=1
    )

    sel_sm = discord.ui.Select(
        placeholder="開始 分",
        custom_id="setup:start_min",
        options=[discord.SelectOption(label=str(i).zfill(2), value=str(i).zfill(2)) for i in range(0,60,5)],
        row=2
    )

    v.add_item(sel_sh)
    v.add_item(sel_sm)

    # --- 3行目 ---
    sel_eh = discord.ui.Select(
        placeholder="終了 時",
        custom_id="setup:end_hour",
        options=[discord.SelectOption(label=str(i), value=str(i)) for i in range(24)],
        row=3
    )

    sel_em = discord.ui.Select(
        placeholder="終了 分",
        custom_id="setup:end_min",
        options=[discord.SelectOption(label=str(i).zfill(2), value=str(i).zfill(2)) for i in range(0,60,5)],
        row=4
    )

    v.add_item(sel_eh)
    v.add_item(sel_em)

    return v