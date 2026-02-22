import asyncio
from datetime import datetime, timedelta
import discord

from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

def setup(bot: discord.Client):

    async def loop():
        await bot.wait_until_ready()

        while not bot.is_closed():
            data = load_data()

            for gid, g in data.get("guilds", {}).items():
                guild_id = int(gid)
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue

                now = datetime.now()

                # ⑤ 終了枠の自動削除（slotを HH:MM として当日比較。日付またぎは簡易対応）
                # 「今より過去の時刻」は消す。ただし深夜またぎがあるので、ここは後で強化もできる。
                to_remove = []
                for s in g.get("slots", []):
                    t = datetime.strptime(s, "%H:%M")
                    slot_time = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

                    # すでに過去なら削除対象
                    if slot_time <= now - timedelta(minutes=1):
                        to_remove.append(s)

                if to_remove:
                    for s in to_remove:
                        if s in g["reservations"]:
                            del g["reservations"][s]
                        if s in g["reminded"]:
                            g["reminded"].remove(s)
                        if s in g["slots"]:
                            g["slots"].remove(s)

                    save_data(data)

                    # パネル更新
                    if g["panel"]["channel_id"] and g["panel"]["message_id"]:
                        ch = bot.get_channel(g["panel"]["channel_id"])
                        if ch:
                            try:
                                msg = await ch.fetch_message(g["panel"]["message_id"])
                                await msg.edit(content=build_panel_text(g), view=SlotView(guild_id=guild_id))
                            except:
                                pass

                # ④ 3分前通知
                notify_ch_id = g.get("notify_channel")
                if notify_ch_id:
                    notify_ch = bot.get_channel(notify_ch_id)
                else:
                    notify_ch = None

                if notify_ch:
                    for s, uid in list(g.get("reservations", {}).items()):
                        if s in g.get("reminded", []):
                            continue

                        t = datetime.strptime(s, "%H:%M")
                        slot_time = now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

                        diff = (slot_time - now).total_seconds()
                        if 0 < diff <= 180:  # 3分以内
                            await notify_ch.send(f"<@{uid}> ⏰ {s} の **3分前**です")
                            g["reminded"].append(s)
                            save_data(data)

            await asyncio.sleep(10)

    bot.loop.create_task(loop())
