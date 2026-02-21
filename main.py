import discord
from discord import app_commands
from discord.ext import commands, tasks
import asyncpg
from datetime import datetime, timedelta

TOKEN = "BOT_TOKEN"
DATABASE_URL = "DATABASE_URL"

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ---------------- DB ----------------
@bot.event
async def on_ready():
    bot.pool = await asyncpg.create_pool(DATABASE_URL)
    await tree.sync()
    reminder.start()
    print("起動")

# ---------------- 枠生成 ----------------
def create_slots(start, end, minutes):
    fmt = "%H:%M"
    s = datetime.strptime(start, fmt)
    e = datetime.strptime(end, fmt)

    slots = []
    while s < e:
        n = s + timedelta(minutes=minutes)
        slots.append(f"{s.strftime(fmt)}〜{n.strftime(fmt)}")
        s = n
    return slots

# ---------------- ボタン ----------------
class SlotButton(discord.ui.Button):
    def __init__(self, slot, reserved_user=None):
        self.slot = slot
        self.reserved_user = reserved_user

        if reserved_user:
            label = f"🔴 {slot}"
            style = discord.ButtonStyle.danger
        else:
            label = f"🟢 {slot}"
            style = discord.ButtonStyle.success

        super().__init__(label=label, style=style)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)
        server = str(interaction.guild.id)

        async with bot.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT user_id FROM reserve WHERE server_id=$1 AND slot=$2",
                server, self.slot
            )

            # 予約
            if not row:
                await conn.execute(
                    """INSERT INTO reserve(server_id, slot, user_id, reminded)
                       VALUES($1,$2,$3,FALSE)""",
                    server, self.slot, user_id
                )

                self.label = f"🔴 {self.slot}"
                self.style = discord.ButtonStyle.danger

                await interaction.message.edit(view=self.view)
                await interaction.followup.send("予約完了", ephemeral=True)

            # キャンセル
            elif row["user_id"] == user_id:
                await conn.execute(
                    "DELETE FROM reserve WHERE server_id=$1 AND slot=$2",
                    server, self.slot
                )

                self.label = f"🟢 {self.slot}"
                self.style = discord.ButtonStyle.success

                await interaction.message.edit(view=self.view)
                await interaction.followup.send("キャンセルしました", ephemeral=True)

            else:
                await interaction.followup.send("すでに予約されています", ephemeral=True)

# ---------------- View ----------------
class SlotView(discord.ui.View):
    def __init__(self, slots, reserves):
        super().__init__(timeout=None)
        reserve_map = {r["slot"]: r["user_id"] for r in reserves}

        for s in slots:
            user = reserve_map.get(s)
            self.add_item(SlotButton(s, user))

# ---------------- create（通知チャンネル指定）----------------
@tree.command(name="create", description="予約枠作成")
async def create(
    interaction: discord.Interaction,
    start: str,
    end: str,
    minutes: int,
    notify_channel: discord.TextChannel
):
    await interaction.response.defer()

    slots = create_slots(start, end, minutes)
    server = str(interaction.guild.id)

    async with bot.pool.acquire() as conn:
        # 枠をDBに保存（通知チャンネルも保存）
        for s in slots:
            await conn.execute("""
            INSERT INTO reserve(server_id, slot, user_id, notify_channel, reminded)
            VALUES($1,$2,NULL,$3,FALSE)
            ON CONFLICT DO NOTHING
            """, server, s, str(notify_channel.id))

        reserves = await conn.fetch(
            "SELECT slot, user_id FROM reserve WHERE server_id=$1",
            server
        )

    view = SlotView(slots, reserves)
    await interaction.followup.send("予約してください", view=view)

# ---------------- 3分前通知（別チャンネル送信）----------------
@tasks.loop(minutes=1)
async def reminder():
    now = datetime.now()

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("""
        SELECT server_id, slot, user_id, notify_channel, reminded
        FROM reserve
        WHERE user_id IS NOT NULL AND reminded=FALSE
        """)

        for r in rows:
            slot_time = datetime.strptime(r["slot"][:5], "%H:%M")
            slot_time = slot_time.replace(
                year=now.year, month=now.month, day=now.day
            )

            diff = (slot_time - now).total_seconds()

            if 0 < diff <= 180:
                ch = bot.get_channel(int(r["notify_channel"]))
                if ch:
                    await ch.send(f"<@{r['user_id']}> 3分後に {r['slot']} 開始")

                    await conn.execute("""
                    UPDATE reserve
                    SET reminded=TRUE
                    WHERE server_id=$1 AND slot=$2
                    """, r["server_id"], r["slot"])

bot.run(TOKEN)
