import discord
import asyncio
from datetime import datetime, timedelta
import json

def load_data():
    try:
        with open("data/data.json", "r") as f:
            return json.load(f)
    except:
        return {"reservations": {}, "reminded": []}

def save_data(data):
    with open("data/data.json", "w") as f:
        json.dump(data, f, indent=2)

def start_remind_loop(bot):

    async def loop():
        await bot.wait_until_ready()

        while not bot.is_closed():
            data = load_data()
            await asyncio.sleep(10)

    bot.loop.create_task(loop())

# ⭐ これを追加
def setup(bot):
    start_remind_loop(bot)
