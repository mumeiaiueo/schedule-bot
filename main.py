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

@bot.event
async def on_ready():
    bot.pool = await asyncpg.create_pool(DATABASE_URL)

    async with bot.pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS reserve(
            server_id TEXT,
            slot TEXT,
            user_id TEXT,
            notify_channel TEXT,
            reminded BOOLEAN DEFAULT FALSE
        );
        """)

        await conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings(
            server_id TEXT PRIMARY KEY,
            notify_channel TEXT
        );
        """)

    await tree.sync()
    reminder.start()
    cleanup.start()
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

# ---------------- 通知チャンネル保存（②）----------------
@tree.command(name="notifyset", description="通知チャンネル設定")
@app_commands.checks.has_permissions(administrator=True)
async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
    async with bot.pool.acquire() as conn:
        await conn.execute("""
        INSERT INTO guild_settings(server_id, notify_channel)
        VALUES($1,$2)
        ON CONFLICT(server_id)
        DO UPDATE SET notify_channel=$2
        """, str(interaction.guild.id), str(channel.id))

    await interaction.response.send_message("通知チャンネル設定完了", ephemeral=True)

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

            if not row:
                await conn.execute(
                    """UPDATE reserve SET user_id=$1, reminded=FALSE
                       WHERE server_id=$2 AND slot=$3""",
                    user_id, server, self.slot
                )

                self.label = f"🔴 {self.slot}"
                self.style = discord.ButtonStyle.danger
                await interaction.message.edit(view=self.view)
                await interaction.followup.send("予約完了", ephemeral=True)

            elif row["user_id"] == user_id:
                await conn.execute(
                    """UPDATE reserve SET user_id=NULL, reminded=FALSE
                       WHERE server_id=$1 AND slot=$2""",
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
            self.add_item(SlotButton(s, reserve_map.get(s)))

# ---------------- create ----------------
@tree.command(name="create", description="予約枠作成")
async def create(interaction: discord.Interaction, start: str, end: str, minutes: int):
    await interaction.response.defer()

    slots = create_slots(start, end, minutes)
    server = str(interaction.guild.id)

    async with bot.pool.acquire() as conn:
        # 通知チャンネル取得
        setting = await conn.fetchrow(
            "SELECT notify_channel FROM guild_settings WHERE server_id=$1",
            server
        )

        if not setting:
            await interaction.followup.send("先に /notifyset をしてください")
            return

        notify_channel = setting["notify_channel"]

        for s in slots:
            await conn.execute("""
            INSERT INTO reserve(server_id, slot, user_id, notify_channel, reminded)
            VALUES($1,$2,NULL,$3,FALSE)
            ON CONFLICT DO NOTHING
            """, server, s, notify_channel)

        reserves = await conn.fetch(
            "SELECT slot, user_id FROM reserve WHERE server_id=$1",
            server
        )

    view = SlotView(slots, reserves)
    await interaction.followup.send("予約してください", view=view)

# ---------------- 3分前通知 ----------------
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

            if 0 < (slot_time - now).total_seconds() <= 180:
                ch = bot.get_channel(int(r["notify_channel"]))
                if ch:
                    await ch.send(f"<@{r['user_id']}> 3分後に {r['slot']} 開始")

                    await conn.execute("""
                    UPDATE reserve SET reminded=TRUE
                    WHERE server_id=$1 AND slot=$2
                    """, r["server_id"], r["slot"])

# ---------------- 自動削除（⑤）----------------
@tasks.loop(minutes=1)
async def cleanup():
    now = datetime.now()

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch("SELECT server_id, slot FROM reserve")

        for r in rows:
            end_time = datetime.strptime(r["slot"][-5:], "%H:%M")
            end_time = end_time.replace(
                year=now.year, month=now.month, day=now.day
            )

            if now > end_time:
                await conn.execute("""
                DELETE FROM reserve
                WHERE server_id=$1 AND slot=$2
                """, r["server_id"], r["slot"])

bot.run(TOKEN)
