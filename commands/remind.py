import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from utils.data_manager import load_data, save_data

JST = ZoneInfo("Asia/Tokyo")

async def start_loop(bot):

    async def loop():
        await bot.wait_until_ready()
        print("✅ remind loop started")

        while not bot.is_closed():
            data = load_data()
            now = datetime.now(JST)

            for gid, g in data.get("guilds", {}).items():
                notify_id = g.get("notify_channel")
                if not notify_id:
                    continue

                ch = bot.get_channel(int(notify_id))
                if not ch:
                    continue

                meta = g.get("meta", {})
                start_min = meta.get("start_min")
                cross_midnight = meta.get("cross_midnight", False)

                reservations = g.get("reservations", {})
                reminded = g.get("reminded", [])

                for slot, uid in list(reservations.items()):
                    if slot in reminded:
                        continue

                    # slot は "HH:MM"
                    h, m = map(int, slot.split(":"))
                    slot_min = h * 60 + m

                    slot_time = now.replace(hour=h, minute=m, second=0, microsecond=0)

                    # 日付またぎ：開始より小さい時刻は翌日扱い
                    if cross_midnight and start_min is not None and slot_min < start_min:
                        slot_time += timedelta(days=1)

                    diff = (slot_time - now).total_seconds()

                    # 🔍 動作確認ログ（必要ならあとで消してOK）
                    print("JST now", now.strftime("%H:%M:%S"), "slot", slot, "diff", int(diff))

                    # 3分前（取りこぼしにくい）
                    if 0 < diff <= 180:
                        await ch.send(f"<@{uid}> ⏰ **{slot} の3分前**です")
                        reminded.append(slot)
                        g["reminded"] = reminded
                        save_data(data)

            await asyncio.sleep(10)

    asyncio.create_task(loop())
