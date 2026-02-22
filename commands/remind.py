from discord.ext import tasks
from datetime import datetime, timedelta, timezone

@tasks.loop(seconds=20)
async def remind_loop(bot):
    now = datetime.now(timezone.utc)
    print("⏱ remind_loop alive:", now.isoformat())  # ← まずこれがログに出るか確認

    # 3分前判定（20秒窓）
    target_from = now + timedelta(minutes=3)
    target_to   = now + timedelta(minutes=3, seconds=20)

    async with bot.pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT s.id, s.guild_id, s.user_id, s.start_at, gs.notify_channel
            FROM slots s
            JOIN guild_settings gs ON gs.guild_id = s.guild_id
            WHERE s.start_at >= $1
              AND s.start_at <  $2
              AND COALESCE(s.notified, false) = false
              AND gs.notify_channel IS NOT NULL
            """,
            target_from, target_to
        )

    print("🔎 remind candidates:", len(rows))

    for r in rows:
        ch = bot.get_channel(int(r["notify_channel"])) or await bot.fetch_channel(int(r["notify_channel"]))
        user_id = int(r["user_id"])
        await ch.send(f"<@{user_id}> あと3分であなたの番です！（start_at={r['start_at']}）")

        async with bot.pool.acquire() as conn:
            await conn.execute("UPDATE slots SET notified=true WHERE id=$1", r["id"])

def start_remind(bot):
    if not remind_loop.is_running():
        remind_loop.start(bot)
        print("✅ remind_loop started")