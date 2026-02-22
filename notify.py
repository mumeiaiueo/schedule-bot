from discord.ext import tasks
from datetime import datetime, timedelta
from storage import load, save

def start_tasks(bot):

    @tasks.loop(minutes=1)
    async def reminder():
        data = load()
        now = datetime.now().strftime("%H:%M")

        delete_list = []

        for slot,v in data["reservations"].items():

            end = v["end"]

            # ⭐ 自動削除
            if end <= now:
                delete_list.append(slot)
                continue

            # ⭐ 3分前通知
            end_dt = datetime.strptime(end,"%H:%M")
            if (end_dt - datetime.now()).seconds <= 180:

                guilds = data["notify"]
                for gid,ch in guilds.items():
                    channel = bot.get_channel(ch)
                    if channel:
                        await channel.send(f"<@{v['user']}> 3分前通知 {slot}")

        for s in delete_list:
            del data["reservations"][s]

        save(data)

    reminder.start()
