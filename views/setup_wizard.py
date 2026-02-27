# views/setup_wizard.py
from __future__ import annotations
import discord

def _fmt(st: dict) -> str:
    day = "未選択" if not st.get("day") else ("今日" if st["day"] == "today" else "明日")
    start = st.get("start") or "未設定"
    end = st.get("end") or "未設定"
    interval = st.get("interval") or "未設定"
    ch = st.get("notify_channel_id")
    ch_txt = f"<#{ch}>" if ch else "未設定"
    everyone = "ON" if st.get("everyone") else "OFF"
    title = st.get("title") or "（なし）"

    return (
        f"📅 日付: **{day}**\n"
        f"🕒 開始: **{start}**\n"
        f"🕘 終了: **{end}**\n"
        f"⏱ 間隔: **{interval}分**\n"
        f"🔔 通知チャンネル: **{ch_txt}**\n"
        f"📣 everyone: **{everyone}**\n"
        f"🏷 タイトル: **{title}**"
    )

def build_setup_embed(st: dict) -> discord.Embed:
    embed = discord.Embed(
        title="🧩 枠作成ウィザード",
        description=_fmt(st),
    )
    embed.set_footer(text="必須: 今日/明日・開始/終了・間隔(20/25/30)・通知チャンネル")
    return embed

def _hour_options():
    return [discord.SelectOption(label=f"{h:02d}", value=f"{h:02d}") for h in range(0, 24)]

def _min_options(step=5):
    arr = []
    m = 0
    while m < 60:
        arr.append(discord.SelectOption(label=f"{m:02d}", value=f"{m:02d}"))
        m += step
    return arr

def build_setup_view(st: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=None)

    # ---- day buttons ----
    b_today = discord.ui.Button(label="今日", style=discord.ButtonStyle.primary if st.get("day")=="today" else discord.ButtonStyle.secondary, custom_id="setup:day:today")
    b_tom = discord.ui.Button(label="明日", style=discord.ButtonStyle.primary if st.get("day")=="tomorrow" else discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow")
    v.add_item(b_today)
    v.add_item(b_tom)

    # ---- start time ----
    s_h = discord.ui.Select(placeholder="開始(時)", min_values=1, max_values=1, options=_hour_options(), custom_id="setup:start_hour")
    s_m = discord.ui.Select(placeholder="開始(分) 5分刻み", min_values=1, max_values=1, options=_min_options(5), custom_id="setup:start_min")
    v.add_item(s_h)
    v.add_item(s_m)

    # ---- end time ----
    e_h = discord.ui.Select(placeholder="終了(時)", min_values=1, max_values=1, options=_hour_options(), custom_id="setup:end_hour")
    e_m = discord.ui.Select(placeholder="終了(分) 5分刻み", min_values=1, max_values=1, options=_min_options(5), custom_id="setup:end_min")
    v.add_item(e_h)
    v.add_item(e_m)

    # ---- interval buttons ----
    for n in (20, 25, 30):
        v.add_item(
            discord.ui.Button(
                label=f"{n}分",
                style=discord.ButtonStyle.success if st.get("interval")==n else discord.ButtonStyle.secondary,
                custom_id=f"setup:interval:{n}",
            )
        )

    # ---- notify channel select ----
    # discord.py 2.x: ChannelSelect が使える場合
    try:
        ch_sel = discord.ui.ChannelSelect(
            placeholder="通知チャンネルを選択（必須）",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
            custom_id="setup:notify_channel",
        )
        v.add_item(ch_sel)
    except Exception:
        # もし古い版でChannelSelect無い場合は、ここはボタンだけにする
        v.add_item(discord.ui.Button(label="通知チャンネル選択が使えません(更新必要)", style=discord.ButtonStyle.danger, custom_id="setup:noop"))

    # ---- optional toggles ----
    v.add_item(discord.ui.Button(
        label=f"everyone: {'ON' if st.get('everyone') else 'OFF'}",
        style=discord.ButtonStyle.danger if st.get("everyone") else discord.ButtonStyle.secondary,
        custom_id="setup:everyone:toggle",
    ))

    v.add_item(discord.ui.Button(
        label="タイトル入力（任意）",
        style=discord.ButtonStyle.secondary,
        custom_id="setup:title:open",
    ))

    # ---- create ----
    v.add_item(discord.ui.Button(
        label="✅ 作成",
        style=discord.ButtonStyle.primary,
        custom_id="setup:create",
    ))

    return v