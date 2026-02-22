import discord
import asyncio
from datetime import datetime, timedelta
from data import load_data, save_data

def start_remind_loop(bot):

    async def loop():
        await bot.wait_until_ready()

        while not bot.is_closed():
            data = load_data()

            if "remind_channel" not in data:
                await asyncio.sleep(30)
                continue

            channel = bot.get_channel(data["remind_channel"])

            now = datetime.now()

            for slot, user_id in list(data["reservations"].items()):
                slot_time = datetime.strptime(slot, "%H:%M")
                slot_time = now.replace(hour=slot_time.hour, minute=slot_time.minute)

                if timedelta(minutes=2, seconds=50) < (slot_time - now) < timedelta(minutes=3):
                    user = await bot.fetch_user(user_id)
                    await channel.send(f"{user.mention} 3分前です")

            await asyncio.sleep(10)

    bot.loop.create_task(loop())
