# views/setup_wizard.py
import discord
from datetime import datetime, timedelta

MINUTES = [f"{m:02d}" for m in range(0, 60, 5)]
HOURS = [f"{h:02d}" for h in range(0, 24)]

def _time_options(prefix: str):
    # value は "HH:MM"
    opts = []
    for h in HOURS:
        for m in MINUTES:
            label = f"{h}:{m}"
            opts.append(discord.SelectOption(label=label, value=label))
    return opts[:25], opts[25:]  # 25制限があるので分割（後でページングしてもOK）

def build_setup_embed(state: dict) -> discord.Embed:
    day = state.get("day") or "未選択"
    start = state.get("start") or "未選択"
    end = state.get("end") or "未選択"
    interval = state.get("interval") or "未選択"
    notify = state.get("notify_channel_id") or "未選択"
    everyone = "ON" if state.get("everyone") else "OFF"
    title = state.get("title") or "（なし）"

    e = discord.Embed(title="🧩 募集枠 作成ウィザード", description="ボタンで順番に選んでね")
    e.add_field(name="① 今日/明日", value=str(day), inline=False)
    e.add_field(name="② 開始", value=str(start), inline=True)
    e.add_field(name="③ 終了", value=str(end), inline=True)
    e.add_field(name="④ 間隔", value=str(interval), inline=False)
    e.add_field(name="⑤ 通知チャンネル（3分前）", value=str(notify), inline=False)
    e.add_field(name="任意：@everyone", value=everyone, inline=True)
    e.add_field(name="任意：タイトル", value=title, inline=True)
    return e

def build_setup_view(state: dict) -> discord.ui.View:
    v = discord.ui.View(timeout=600)

    # --- 今日/明日 ---
    v.add_item(discord.ui.Button(
        label="今日", style=discord.ButtonStyle.primary,
        custom_id="setup:day:today"
    ))
    v.add_item(discord.ui.Button(
        label="明日", style=discord.ButtonStyle.secondary,
        custom_id="setup:day:tomorrow"
    ))

    # --- 時刻（開始/終了）: 5分刻み ---
    # Selectは25件制限があるので、とりあえず「00:00〜12:00」「12:05〜23:55」で分ける
    opts1 = []
    opts2 = []
    for h in range(0, 12):
        for m in range(0, 60, 5):
            label = f"{h:02d}:{m:02d}"
            opts1.append(discord.SelectOption(label=label, value=label))
    for h in range(12, 24):
        for m in range(0, 60, 5):
            label = f"{h:02d}:{m:02d}"
            opts2.append(discord.SelectOption(label=label, value=label))

    # 開始（前半/後半）
    v.add_item(discord.ui.Select(
        placeholder="開始時刻（0:00〜11:55）",
        options=opts1[:25],
        custom_id="setup:start:am"
    ))
    v.add_item(discord.ui.Select(
        placeholder="開始時刻（12:00〜23:55）",
        options=opts2[:25],
        custom_id="setup:start:pm"
    ))

    # 終了（前半/後半）
    v.add_item(discord.ui.Select(
        placeholder="終了時刻（0:00〜11:55）",
        options=opts1[:25],
        custom_id="setup:end:am"
    ))
    v.add_item(discord.ui.Select(
        placeholder="終了時刻（12:00〜23:55）",
        options=opts2[:25],
        custom_id="setup:end:pm"
    ))

    # --- 間隔 ---
    v.add_item(discord.ui.Button(label="20分", style=discord.ButtonStyle.success, custom_id="setup:interval:20"))
    v.add_item(discord.ui.Button(label="25分", style=discord.ButtonStyle.success, custom_id="setup:interval:25"))
    v.add_item(discord.ui.Button(label="30分", style=discord.ButtonStyle.success, custom_id="setup:interval:30"))

    # --- 通知チャンネル選択（ChannelSelect）---
    v.add_item(discord.ui.ChannelSelect(
        channel_types=[discord.ChannelType.text],
        placeholder="通知チャンネル（3分前）を選ぶ",
        custom_id="setup:notify_channel"
    ))

    # --- 任意 ---
    v.add_item(discord.ui.Button(
        label="@everyone 切替", style=discord.ButtonStyle.secondary,
        custom_id="setup:everyone:toggle"
    ))
    v.add_item(discord.ui.Button(
        label="タイトル入力（任意）", style=discord.ButtonStyle.secondary,
        custom_id="setup:title:modal"
    ))

    # --- 作成 ---
    v.add_item(discord.ui.Button(
        label="✅ 作成する", style=discord.ButtonStyle.danger,
        custom_id="setup:create"
    ))

    return v