# views/setup_wizard.py
import discord

MINUTE_VALUES = [f"{m:02d}" for m in range(0, 60, 5)]
HOUR_VALUES = [f"{h:02d}" for h in range(0, 24)]

def build_setup_embed(state: dict) -> discord.Embed:
    day = state.get("day") or "未選択"
    start = state.get("start") or "未選択"
    end = state.get("end") or "未選択"
    interval = state.get("interval") or "未選択"
    notify = state.get("notify_channel_id") or "未選択"
    everyone = "ON" if state.get("everyone") else "OFF"
    title = state.get("title") or "（なし）"

    e = discord.Embed(title="🧩 募集枠 作成ウィザード", description="ボタン/セレクトで順番に選んでね")
    e.add_field(name="① 今日/明日", value=str(day), inline=False)
    e.add_field(name="② 開始時刻", value=str(start), inline=True)
    e.add_field(name="③ 終了時刻", value=str(end), inline=True)
    e.add_field(name="④ 間隔(20/25/30)", value=str(interval), inline=False)
    e.add_field(name="⑤ 通知チャンネル（3分前）", value=str(notify), inline=False)
    e.add_field(name="任意：@everyone", value=everyone, inline=True)
    e.add_field(name="任意：タイトル", value=title, inline=True)
    return e

def build_setup_view(state: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=600)

    # ---- 今日/明日 ----
    v.add_item(discord.ui.Button(label="今日", style=discord.ButtonStyle.primary, custom_id="setup:day:today"))
    v.add_item(discord.ui.Button(label="明日", style=discord.ButtonStyle.secondary, custom_id="setup:day:tomorrow"))

    # ---- 開始（時間）----
    v.add_item(discord.ui.Select(
        placeholder="開始：時間(0-23)",
        options=[discord.SelectOption(label=h, value=h) for h in HOUR_VALUES],
        custom_id="setup:start_hour"
    ))
    # ---- 開始（分）----
    v.add_item(discord.ui.Select(
        placeholder="開始：分(00/05/10...)",
        options=[discord.SelectOption(label=m, value=m) for m in MINUTE_VALUES],
        custom_id="setup:start_min"
    ))

    # ---- 終了（時間）----
    v.add_item(discord.ui.Select(
        placeholder="終了：時間(0-23)",
        options=[discord.SelectOption(label=h, value=h) for h in HOUR_VALUES],
        custom_id="setup:end_hour"
    ))
    # ---- 終了（分）----
    v.add_item(discord.ui.Select(
        placeholder="終了：分(00/05/10...)",
        options=[discord.SelectOption(label=m, value=m) for m in MINUTE_VALUES],
        custom_id="setup:end_min"
    ))

    # ---- 間隔 ----
    v.add_item(discord.ui.Button(label="20分", style=discord.ButtonStyle.success, custom_id="setup:interval:20"))
    v.add_item(discord.ui.Button(label="25分", style=discord.ButtonStyle.success, custom_id="setup:interval:25"))
    v.add_item(discord.ui.Button(label="30分", style=discord.ButtonStyle.success, custom_id="setup:interval:30"))

    # ---- 通知チャンネル（必須）----
    v.add_item(discord.ui.ChannelSelect(
        channel_types=[discord.ChannelType.text],
        placeholder="通知チャンネル（3分前）を選ぶ",
        custom_id="setup:notify_channel"
    ))

    # ---- 任意 ----
    v.add_item(discord.ui.Button(label="@everyone 切替", style=discord.ButtonStyle.secondary, custom_id="setup:everyone:toggle"))
    v.add_item(discord.ui.Button(label="タイトル（任意）※後で実装可", style=discord.ButtonStyle.secondary, custom_id="setup:title:skip"))

    # ---- 作成 ----
    v.add_item(discord.ui.Button(label="✅ 作成する", style=discord.ButtonStyle.danger, custom_id="setup:create"))

    return v