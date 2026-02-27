# views/setup_wizard.py  (discord.py 2.x 対応 / ActionRow 不使用)
import discord

HOURS = [f"{h:02d}" for h in range(0, 24)]
MINS_5 = [f"{m:02d}" for m in range(0, 60, 5)]  # 5分刻み


def _val_or_dash(v):
    return v if v is not None else "—"


def build_setup_embed(st: dict) -> discord.Embed:
    day = st.get("day")
    day_txt = "今日" if day == "today" else ("明日" if day == "tomorrow" else "未選択")

    start = None
    end = None
    if st.get("start_hour") and st.get("start_min"):
        start = f"{st['start_hour']}:{st['start_min']}"
    if st.get("end_hour") and st.get("end_min"):
        end = f"{st['end_hour']}:{st['end_min']}"

    interval = st.get("interval")
    notify = st.get("notify_channel_id")
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "（なし）"

    e = discord.Embed(
        title="🧩 枠作成ウィザード",
        description="ボタン/セレクトで選んでね（必須が揃うと作成できます）",
    )
    e.add_field(name="📅 今日/明日（必須）", value=day_txt, inline=False)
    e.add_field(name="🕒 開始（必須）", value=_val_or_dash(start), inline=True)
    e.add_field(name="🕘 終了（必須）", value=_val_or_dash(end), inline=True)
    e.add_field(name="⏱ 間隔（必須）", value=_val_or_dash(str(interval) if interval else None), inline=True)
    e.add_field(name="📣 3分前通知チャンネル（必須）", value=(f"<#{notify}>" if notify else "未設定"), inline=False)
    e.add_field(name="📢 everyone（任意）", value=everyone, inline=True)
    e.add_field(name="📝 タイトル（任意）", value=title, inline=True)
    e.set_footer(text="※時間は 5分刻み（00/05/10...）")
    return e


class TitleModal(discord.ui.Modal, title="タイトル入力（任意）"):
    title_input = discord.ui.TextInput(
        label="タイトル",
        required=False,
        max_length=50,
        placeholder="例：夜の部 / ランク募集 / 参加者募集 など",
    )

    def __init__(self, bot_client, st: dict, message: discord.Message):
        super().__init__()
        self.bot_client = bot_client
        self.st = st
        self.message = message

    async def on_submit(self, interaction: discord.Interaction):
        self.st["title"] = str(self.title_input.value).strip() or None
        await interaction.response.defer(ephemeral=True)
        await self.bot_client.refresh_setup_message(self.message, self.st)
        try:
            await interaction.followup.send("✅ タイトルを更新しました", ephemeral=True)
        except Exception:
            pass


def build_setup_view(st: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=300)

    # --- 今日/明日 (row 0) ---
    v.add_item(discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today", row=0))
    v.add_item(discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow", row=0))

    # --- 開始 (row 1,2) ---
    v.add_item(discord.ui.Select(
        placeholder="開始: 時",
        custom_id="setup:start_hour",
        options=[discord.SelectOption(label=h, value=h) for h in HOURS],
        min_values=1, max_values=1,
        row=1,
    ))
    v.add_item(discord.ui.Select(
        placeholder="開始: 分（5分刻み）",
        custom_id="setup:start_min",
        options=[discord.SelectOption(label=m, value=m) for m in MINS_5],
        min_values=1, max_values=1,
        row=2,
    ))

    # --- 終了 (row 3,4) ---
    v.add_item(discord.ui.Select(
        placeholder="終了: 時",
        custom_id="setup:end_hour",
        options=[discord.SelectOption(label=h, value=h) for h in HOURS],
        min_values=1, max_values=1,
        row=3,
    ))
    v.add_item(discord.ui.Select(
        placeholder="終了: 分（5分刻み）",
        custom_id="setup:end_min",
        options=[discord.SelectOption(label=m, value=m) for m in MINS_5],
        min_values=1, max_values=1,
        row=4,
    ))

    # --- 間隔 (row 5) ---
    v.add_item(discord.ui.Button(label="20分", style=discord.ButtonStyle.success, custom_id="setup:interval:20", row=5))
    v.add_item(discord.ui.Button(label="25分", style=discord.ButtonStyle.success, custom_id="setup:interval:25", row=5))
    v.add_item(discord.ui.Button(label="30分", style=discord.ButtonStyle.success, custom_id="setup:interval:30", row=5))

    # --- 通知チャンネル (row 6) ---
    # ChannelSelect は discord.py のバージョンで無いことがあるので try
    try:
        v.add_item(discord.ui.ChannelSelect(
            placeholder="3分前通知チャンネル（必須）",
            custom_id="setup:notify_channel",
            channel_types=[discord.ChannelType.text],
            min_values=1, max_values=1,
            row=6,
        ))
    except Exception:
        # もし無ければ、ここは「コマンドで設定」にする必要がある（後で対応）
        v.add_item(discord.ui.Button(
            label="⚠️通知チャンネル選択が未対応（discord.py更新必要）",
            style=discord.ButtonStyle.secondary,
            custom_id="setup:notify_channel_unavailable",
            row=6
        ))

    # --- 任意 (row 7) ---
    v.add_item(discord.ui.Button(label="everyone切替（任意）", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle", row=7))
    v.add_item(discord.ui.Button(label="タイトル入力（任意）", style=discord.ButtonStyle.secondary, custom_id="setup:title:open", row=7))

    # --- 作成/キャンセル (row 8) ---
    v.add_item(discord.ui.Button(label="✅ 作成", style=discord.ButtonStyle.primary, custom_id="setup:create", row=8))
    v.add_item(discord.ui.Button(label="✖ キャンセル", style=discord.ButtonStyle.danger, custom_id="setup:cancel", row=8))

    return v