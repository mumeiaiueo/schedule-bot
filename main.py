import os
import discord
import asyncio
from datetime import datetime, timedelta
import json

def load_data():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("data/data.json"):
        with open("data/data.json", "w") as f:
            json.dump({"reservations": {}, "reminded": []}, f)

    with open("data/data.json", "r") as f:
        return json.load(f)

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open("data/data.json", "w") as f:
        json.dump(data, f, indent=2)

def start_remind_loop(bot):

    async def loop():
        await bot.wait_until_ready()

        while not bot.is_closed():
            data = load_data()

            if "remind_channel" not in data:
                await asyncio.sleep(30)
                continue

            channel = bot.get_channel(data["remind_channel"])
            if channel is None:
                await asyncio.sleep(30)
                continue

            now = datetime.now()

            if "reminded" not in data:
                data["reminded"] = []

            for slot, user_id in list(data.get("reservations", {}).items()):
                try:
                    slot_time = datetime.strptime(slot, "%H:%M")
                    slot_time = now.replace(hour=slot_time.hour, minute=slot_time.minute, second=0)

                    if slot_time < now:
                        continue

                    diff = slot_time - now

                    # ⭐ 3分前 & 未通知
                    if timedelta(minutes=2, seconds=50) < diff <= timedelta(minutes=3) and slot not in data["reminded"]:
                        user = await bot.fetch_user(int(user_id))
                        await channel.send(f"{user.mention} 3分前です")

                        data["reminded"].append(slot)
                        save_data(data)

                except Exception as e:
                    print("remind error:", e)

            await asyncio.sleep(10)

    bot.loop.create_task(loop())
