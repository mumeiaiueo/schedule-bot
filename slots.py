from discord.ext import commands
from datetime import datetime, timedelta
from views import SlotView

async def setup(bot):

    @bot.command()
    async def slots(ctx, start: str, end: str, interval: int):

        if interval not in [20,25,30]:
            await ctx.send("❌ 20・25・30のみ")
            return

        try:
            start_time = datetime.strptime(start,"%H:%M")
            end_time = datetime.strptime(end,"%H:%M")
        except:
            await ctx.send("❌ 10:00形式")
            return

        current = start_time

        while current + timedelta(minutes=interval) <= end_time:
            nxt = current + timedelta(minutes=interval)

            slot = f"{current.strftime('%H:%M')}〜{nxt.strftime('%H:%M')}"
            view = SlotView(slot, nxt.strftime("%H:%M"))

            await ctx.send(f"🟢 {slot}", view=view)
            current = nxt
