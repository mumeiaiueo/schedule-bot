import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import asyncpg
import os

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------- DB ----------
async def create_db():
    return await asyncpg.create_pool(DATABASE_URL)

# ---------- SLOT ----------
def create_slots(start_str, end_str, minutes):
    start = datetime.strptime(start_str, "%H:%M")
    end = datetime.strptime(end_str, "%H:%M")

    slots = []
    cur = start
    while cur < end:
        nxt = cur + timedelta(minutes=minutes)
        if nxt > end:
            break
        slots.append(f"{cur.strftime('%H:%M')}〜{nxt.strftime('%H:%M')}")
        cur = nxt
    return slots

# ---------- BUTTON ----------
class SlotButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        slot = self.label
        user = str(interaction.user.id)
        server = str(interaction.guild.id)

        try:
            async with bot.pool.acquire() as conn:
                await conn.execute(
                    "INSERT INTO reserve(server_id, slot, user_id) VALUES($1,$2,$3)",
                    server, slot, user
                )

            self.disabled = True
            self.label = f"🔒 {slot}"
            self.style = discord.ButtonStyle.secondary

            await interaction.message.edit(view=self.view)
            await interaction.followup.send("予約完了", ephemeral=True)

        except:
            await interaction.followup.send("この枠は埋まっています", ephemeral=True)

class CancelButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=f"❌ {label}", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        slot = self.label.replace("❌ ", "")
        user = str(interaction.user.id)
        server = str(interaction.guild.id)

        async with bot.pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM reserve WHERE server_id=$1 AND slot=$2 AND user_id=$3",
                server, slot, user
            )

        for item in self.view.children:
            if isinstance(item, SlotButton) and slot in item.label:
                item.disabled = False
                item.label = slot
                item.style = discord.ButtonStyle.primary

        await interaction.message.edit(view=self.view)
        await interaction.followup.send("キャンセルしました", ephemeral=True)

class SlotView(discord.ui.View):
    def __init__(self, slots):
        super().__init__(timeout=None)
        for s in slots:
            self.add_item(SlotButton(s))
            self.add_item(CancelButton(s))

# ---------- SLASH ----------
@tree.command(name="create", description="予約枠作成")
@app_commands.choices(minutes=[
    app_commands.Choice(name="20分", value=20),
    app_commands.Choice(name="25分", value=25),
    app_commands.Choice(name="30分", value=30),
])
async def create(interaction: discord.Interaction, start: str, end: str, minutes: app_commands.Choice[int]):
    await interaction.response.defer()

    slots = create_slots(start, end, minutes.value)
    view = SlotView(slots)

    await interaction.followup.send("予約してください", view=view)

@tree.command(name="notifyset", description="通知チャンネル設定")
@app_commands.checks.has_permissions(administrator=True)
async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
    await interaction.response.defer(ephemeral=True)

    server = str(interaction.guild.id)

    async with bot.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO guild_settings(server_id, notify_channel)
            VALUES($1,$2)
            ON CONFLICT(server_id)
            DO UPDATE SET notify_channel=$2
        """, server, str(channel.id))

    await interaction.followup.send("設定完了", ephemeral=True)

@tree.command(name="myreserve", description="自分の予約")
async def myreserve(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    user = str(interaction.user.id)
    server = str(interaction.guild.id)

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT slot FROM reserve WHERE server_id=$1 AND user_id=$2",
            server, user
        )

    text = "予約なし" if not rows else "\n".join([r["slot"] for r in rows])
    await interaction.followup.send(text, ephemeral=True)

# ---------- REMIND ----------
@tasks.loop(seconds=60)
async def remind():
    now = datetime.now()

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM reserve")

    for row in rows:
        slot = row["slot"]
        user = row["user_id"]
        server = row["server_id"]

        start = slot.split("〜")[0]
        notify_time = datetime.strptime(start, "%H:%M") - timedelta(minutes=3)

        if notify_time.strftime("%H:%M") == now.strftime("%H:%M"):

            async with bot.pool.acquire() as conn:
                setting = await conn.fetchrow(
                    "SELECT notify_channel FROM guild_settings WHERE server_id=$1",
                    server
                )

            if setting:
                channel = bot.get_channel(int(setting["notify_channel"]))
                if channel:
                    await channel.send(f"<@{user}> さん 3分前です")

# ---------- READY ----------
@bot.event
async def on_ready():
    bot.pool = await create_db()
    bot.add_view(SlotView([]))
    await tree.sync()
    remind.start()
    print("READY")

bot.run(TOKEN)
