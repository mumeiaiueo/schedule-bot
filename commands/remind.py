import asyncio
from datetime import datetime, timedelta
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

async def start_loop(bot):

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

                # 3分前通知
                notify_id = g.get("notify_channel")
                if notify_id:
                    channel = bot.get_channel(notify_id)
                else:
                    channel = None

                if channel:
                    for slot, uid in g.get("reservations", {}).items():
                        if slot in g.get("reminded", []):
                            continue

                        t = datetime.strptime(slot, "%H:%M")
                        slot_time = now.replace(hour=t.hour, minute=t.minute)

                        diff = (slot_time - now).total_seconds()
                        if 0 < diff <= 180:
                            await channel.send(f"<@{uid}> 3分前です")
                            g["reminded"].append(slot)
                            save_data(data)

            await asyncio.sleep(10)

    asyncio.create_task(loop())
