import os
import discord
import asyncpg
import pytz
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
JST = pytz.timezone("Asia/Tokyo")
# 予約データ
reservations = {}

# ========= 予約ボタン =========
class ReserveButton(discord.ui.Button):
    def __init__(self, time_label):
        super().__init__(
            label=f"{time_label} 予約可",
            style=discord.ButtonStyle.green
        )
        self.time_label = time_label

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user

        # 空きなら予約
        if self.time_label not in reservations:
            reservations[self.time_label] = user.id
            self.label = f"{self.time_label} {user.display_name}"
            self.style = discord.ButtonStyle.red
            await interaction.response.edit_message(view=self.view)
            return

        # 既に予約済み
        if reservations[self.time_label] == user.id:
            # 自分ならキャンセル
            del reservations[self.time_label]
            self.label = f"{self.time_label} 予約可"
            self.style = discord.ButtonStyle.green
            await interaction.response.edit_message(view=self.view)
        else:
            await interaction.response.send_message(
                "❌ 既に予約されています",
                ephemeral=True
            )

# ========= View =========
class ReserveView(discord.ui.View):
    def __init__(self, times):
        super().__init__(timeout=None)
        for t in times:
            self.add_item(ReserveButton(t))

# ========= 時間生成 =========
def generate_times(start, end, interval):
    times = []
    current = start
    while current < end:
        times.append(current.strftime("%H:%M"))
        current += timedelta(minutes=interval)
    return times

# ========= コマンド =========
@bot.command()
async def 作成(ctx, start: str, end: str, interval: int):
    """
    例
    !作成 10:00 12:00 20
    """

    start_dt = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")

    times = generate_times(start_dt, end_dt, interval)

    view = ReserveView(times)
    await ctx.send("予約パネル", view=view)

bot.run("TOKEN")
