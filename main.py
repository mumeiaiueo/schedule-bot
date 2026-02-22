import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
import json
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

FILE = "reservations.json"

# ===== 永続化 =====
def load_data():
    if not os.path.exists(FILE):
        return {}
    with open(FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(FILE, "w") as f:
        json.dump(data, f)

reservations = load_data()
panel_message = None

# ===== パネル更新 =====
async def update_panel(channel):
    global panel_message

    text = "📅 **予約一覧**\n"
    for slot, uid in reservations.items():
        if uid:
            text += f"🔴 {slot} <@{uid}>\n"
        else:
            text += f"🟢 {slot}\n"

    if panel_message:
        await panel_message.edit(content=text)
    else:
        panel_message = await channel.send(text)

# ===== View =====
class SlotView(discord.ui.View):
    def __init__(self, slot):
        super().__init__(timeout=None)
        self.slot = slot

    @discord.ui.button(label="予約する", style=discord.ButtonStyle.success)
    async def reserve(self, interaction: discord.Interaction, button: discord.ui.Button):

        user = interaction.user

        # ===== 重複予約防止 =====
        if str(user.id) in reservations.values():
            await interaction.response.send_message("❌ 他枠予約中", ephemeral=True)
            return

        if reservations[self.slot]:
            await interaction.response.send_message("❌ 既に埋まり", ephemeral=True)
            return

        reservations[self.slot] = str(user.id)
        save_data(reservations)

        button.label = f"埋まり:{user.display_name}"
        button.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(view=self)
        await update_panel(interaction.channel)

    @discord.ui.button(label="キャンセル", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):

        if reservations[self.slot] != str(interaction.user.id):
            await interaction.response.send_message("❌ 自分の予約のみ", ephemeral=True)
            return

        reservations[self.slot] = None
        save_data(reservations)

        for child in self.children:
            if isinstance(child, discord.ui.Button) and "埋まり" in child.label:
                child.label = "予約する"
                child.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self)
        await update_panel(interaction.channel)

    @discord.ui.button(label="管理削除", style=discord.ButtonStyle.danger)
    async def force(self, interaction: discord.Interaction, button: discord.ui.Button):

        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ", ephemeral=True)
            return

        reservations[self.slot] = None
        save_data(reservations)

        for child in self.children:
            if isinstance(child, discord.ui.Button) and "埋まり" in child.label:
                child.label = "予約する"
                child.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self)
        await update_panel(interaction.channel)

# ===== 予約枠生成 =====
@bot.command()
async def slots(ctx, start: str, end: str, interval: int):

    if interval not in [20, 25, 30]:
        await ctx.send("❌ 20・25・30のみ")
        return

    start_time = datetime.strptime(start, "%H:%M")
    end_time = datetime.strptime(end, "%H:%M")

    current = start_time
    while current + timedelta(minutes=interval) <= end_time:
        next_time = current + timedelta(minutes=interval)
        slot = f"{current.strftime('%H:%M')}〜{next_time.strftime('%H:%M')}"

        reservations.setdefault(slot, None)
        save_data(reservations)

        await ctx.send(f"🟢 {slot}", view=SlotView(slot))
        current = next_time

    await update_panel(ctx.channel)

# ===== 5分前通知 =====
@tasks.loop(minutes=1)
async def reminder():

    now = datetime.now().strftime("%H:%M")

    for slot, uid in reservations.items():
        if not uid:
            continue

        start = slot.split("〜")[0]
        dt_start = datetime.strptime(start, "%H:%M")
        dt_now = datetime.strptime(now, "%H:%M")

        if 0 <= (dt_start - dt_now).seconds <= 300:
            for g in bot.guilds:
                channel = g.text_channels[0]
                await channel.send(f"<@{uid}> 5分前")

# ===== 自動削除 =====
@tasks.loop(minutes=1)
async def auto_delete():

    now = datetime.now().strftime("%H:%M")

    delete = []
    for slot in reservations:
        end = slot.split("〜")[1]
        if end <= now:
            delete.append(slot)

    for s in delete:
        del reservations[s]

    save_data(reservations)

@bot.event
async def on_ready():
    reminder.start()
    auto_delete.start()
    print("起動成功")

TOKEN = os.getenv("TOKEN")
bot.run(TOKEN)
