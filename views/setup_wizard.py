import discord

# ------------------------------
# 表示（Embed）
# ------------------------------
def build_setup_embed(state: dict) -> discord.Embed:
    day = "未選択" if not state.get("day") else ("今日" if state["day"] == "today" else "明日")
    start = state.get("start") or "未設定"
    end = state.get("end") or "未設定"
    interval = state.get("interval") or "未設定"
    notify = state.get("notify_channel_id") or "未設定"
    everyone = "ON" if state.get("everyone") else "OFF"
    title = state.get("title") or "（なし）"

    e = discord.Embed(
        title="🛠 枠作成ウィザード",
        description="ボタン/セレクトで設定して、最後に **作成** を押してね。",
        color=0x5865F2,
    )

    e.add_field(name="📅 日付", value=day, inline=True)
    e.add_field(name="⏱ 間隔", value=str(interval), inline=True)
    e.add_field(name="🔔 通知チャンネル", value=f"<#{notify}>" if notify != "未設定" else "未設定", inline=True)

    e.add_field(name="🟢 開始", value=start, inline=True)
    e.add_field(name="🔴 終了", value=end, inline=True)
    e.add_field(name="@everyone", value=everyone, inline=True)

    e.add_field(name="📝 タイトル（任意）", value=title, inline=False)

    e.set_footer(text="必須：今日/明日・開始/終了・間隔(20/25/30)・通知チャンネル")
    return e


# ------------------------------
# UI（View）
# ------------------------------
def _hour_options():
    # 00〜23
    return [discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}") for h in range(24)]


def _min_options():
    # 5分刻み（今の感じ）
    mins = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]
    return [discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}") for m in mins]


def build_setup_view(state: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=600)

    # --- 今日/明日ボタン ---
    b_today = discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today")
    b_tomo = discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow")
    v.add_item(b_today)
    v.add_item(b_tomo)

    # --- 開始 hour/min ---
    v.add_item(_Select(custom_id="setup:start_hour", placeholder="開始：時", options=_hour_options()))
    v.add_item(_Select(custom_id="setup:start_min", placeholder="開始：分(5刻み)", options=_min_options()))

    # --- 終了 hour/min ---
    v.add_item(_Select(custom_id="setup:end_hour", placeholder="終了：時", options=_hour_options()))
    v.add_item(_Select(custom_id="setup:end_min", placeholder="終了：分(5刻み)", options=_min_options()))

    # --- 間隔ボタン 20/25/30 ---
    v.add_item(discord.ui.Button(label="20分", style=discord.ButtonStyle.success, custom_id="setup:interval:20"))
    v.add_item(discord.ui.Button(label="25分", style=discord.ButtonStyle.success, custom_id="setup:interval:25"))
    v.add_item(discord.ui.Button(label="30分", style=discord.ButtonStyle.success, custom_id="setup:interval:30"))

    # --- 通知チャンネル（必須） ---
    v.add_item(discord.ui.ChannelSelect(
        channel_types=[discord.ChannelType.text],
        placeholder="通知チャンネル（必須）を選ぶ",
        min_values=1,
        max_values=1,
        custom_id="setup:notify_channel",
    ))

    # --- everyone 任意 ---
    v.add_item(discord.ui.Button(label="@everyone 切替（任意）", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle"))

    # --- 作成 ---
    v.add_item(discord.ui.Button(label="✅ 作成", style=discord.ButtonStyle.primary, custom_id="setup:create"))

    return v


# discord.ui.Select をちょい簡単にする薄いラッパ
class _Select(discord.ui.Select):
    def __init__(self, custom_id: str, placeholder: str, options: list[discord.SelectOption]):
        super().__init__(custom_id=custom_id, placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        # main.py 側で on_interaction が全部処理するのでここは空でOK
        pass