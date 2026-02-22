import os
import discord
from discord.ext import commands, tasks
from datetime import datetime
from zoneinfo import ZoneInfo

from utils.data_manager import load_data, save_data
from views.slot_view import SlotView

TOKEN = os.getenv("TOKEN")
JST = ZoneInfo("Asia/Tokyo")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# コマンド登録
from commands.create import setup as create_setup
from commands.remind import setup as remind_setup

create_setup(bot)
remind_setup(bot)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print("起動完了")

    # 既存ギルドのViewを登録（再起動後もボタン復活）
    data = load_data()
    for gid in data.get("guilds", {}).keys():
        bot.add_view(SlotView(int(gid)))

    tick.start()

@tasks.loop(seconds=10)
async def tick():
    """
    ✅ 3分前通知（remind_channelが設定されている時だけ）
    ✅ 終了した枠の自動削除
    ✅ パネルを必要なら更新
    """
    data = load_data()
    now = datetime.now(JST)
    changed_any = False

    for gid_str, g in data.get("guilds", {}).items():
        gid = int(gid_str)

        slots = g.get("slots", [])
        reservations = g.get("reservations", {})
        reminded = set(g.get("reminded", []))
        remind_ch_id = g.get("remind_channel_id")

        changed = False

        # --- 自動削除（終了した枠を消す）---
        new_slots = []
        for s in slots:
            end_dt = datetime.fromisoformat(s["end_iso"])
            if end_dt <= now:
                sid = s["id"]
                reservations.pop(sid, None)
                reminded.discard(sid)
                changed = True
            else:
                new_slots.append(s)

        if changed:
            g["slots"] = new_slots
            g["reservations"] = reservations
            g["reminded"] = list(reminded)

        # --- 3分前通知 ---
        if remind_ch_id:
            ch = bot.get_channel(int(remind_ch_id))
            if ch:
                for s in g.get("slots", []):
                    sid = s["id"]
                    if sid not in reservations:
                        continue

                    start_dt = datetime.fromisoformat(s["start_iso"])
                    diff = (start_dt - now).total_seconds()

                    # 180秒±10秒
                    if 170 <= diff <= 190 and sid not in reminded:
                        uid = reservations[sid]
                        await ch.send(f"<@{uid}> 3分前です：{s['start_iso'][11:16]}")
                        reminded.add(sid)
                        g["reminded"] = list(reminded)
                        changed = True

        # --- パネル更新（変化があった時だけ）---
        if changed and g.get("panel_channel_id") and g.get("panel_message_id"):
            channel = bot.get_channel(int(g["panel_channel_id"]))
            if channel:
                try:
                    msg = await channel.fetch_message(int(g["panel_message_id"]))
                    lines = ["📅 予約枠"]
                    for s in g.get("slots", []):
                        hhmm = s["start_iso"][11:16]
                        sid = s["id"]
                        if sid in reservations:
                            lines.append(f"🔴 {hhmm} <@{reservations[sid]}>")
                        else:
                            lines.append(f"🟢 {hhmm}")
                    await msg.edit(content="\n".join(lines), view=SlotView(gid))
                except Exception:
                    pass

        if changed:
            changed_any = True

    if changed_any:
        save_data(data)

bot.run(TOKEN)
