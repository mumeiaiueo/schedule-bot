import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = ZoneInfo("Asia/Tokyo")

async def start_loop(bot):

    async def loop():
        await bot.wait_until_ready()

        while not bot.is_closed():
            data = load_data()

            for gid, g in data.get("guilds", {}).items():
                guild_id = int(gid)

                now = datetime.now(JST)

                notify_id = g.get("notify_channel")
                notify_ch = bot.get_channel(notify_id) if notify_id else None

                meta = g.get("meta", {})
                start_min = meta.get("start_min")
                cross_midnight = meta.get("cross_midnight", False)

                # 3分前通知
                if notify_ch:
                    for slot, uid in list(g.get("reservations", {}).items()):
                        if slot in g.get("reminded", []):
                            continue

                        h, m = map(int, slot.split(":"))
                        slot_min = h * 60 + m

                        slot_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

                        # ⭐ 日付またぎの場合：開始より小さい時刻は「翌日」扱い
                        if cross_midnight and start_min is not None and slot_min < start_min:
                            slot_time += timedelta(days=1)

                        diff = (slot_time - now).total_seconds()

                        # ⭐ 安全に拾う（ズレても拾う）
                        if 0 < diff <= 180:
                            await notify_ch.send(f"<@{uid}> ⏰ **{slot} の3分前**です")
                            g["reminded"].append(slot)
                            save_data(data)

                # ⑤ 時間が過ぎた枠の自動削除（予約済みだけ消す版）
                # ※「枠自体も消したい」なら後で拡張する
                for slot, uid in list(g.get("reservations", {}).items()):
                    h, m = map(int, slot.split(":"))
                    slot_min = h * 60 + m

                    slot_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    if cross_midnight and start_min is not None and slot_min < start_min:
                        slot_time += timedelta(days=1)

                    # 開始時刻を過ぎたら予約を消す（必要なら+intervalで「終了後」にできる）
                    if now >= slot_time:
                        del g["reservations"][slot]
                        if slot in g.get("reminded", []):
                            g["reminded"].remove(slot)
                        save_data(data)

                        # パネル更新（あれば）
                        ch_id = g.get("panel", {}).get("channel_id")
                        msg_id = g.get("panel", {}).get("message_id")
                        if ch_id and msg_id:
                            ch = bot.get_channel(ch_id)
                            if ch:
                                try:
                                    msg = await ch.fetch_message(msg_id)
                                    await msg.edit(content=build_panel_text(g), view=SlotView(guild_id=guild_id, page=0))
                                except:
                                    pass

            await asyncio.sleep(10)

    asyncio.create_task(loop())
