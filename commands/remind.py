from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback
import discord

@tasks.loop(seconds=20)
async def remind_loop(bot):
    try:
        now = datetime.now(timezone.utc)
        print("⏱ remind_loop alive:", now.isoformat())

        # テスト用：今から10分以内全部拾う
        target_from = now - timedelta(minutes=1)
        target_to   = now + timedelta(minutes=10)

        async with bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.guild_id, s.user_id, s.start_at, gs.notify_channel
                FROM slots s
                JOIN guild_settings gs ON gs.guild_id = s.guild_id::text
                WHERE s.start_at >= $1
                  AND s.start_at <  $2
                  AND COALESCE(s.notified, false) = false
                  AND gs.notify_channel IS NOT NULL
                """,
                target_from,
                target_to
            )

        print("🔎 remind candidates:", len(rows))
        if rows:
            print("🔎 sample row:", dict(rows[0]))

        for r in rows:
            try:
                notify_channel = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(notify_channel)
                if ch is None:
                    ch = await bot.fetch_channel(notify_channel)

                await ch.send(f"<@{user_id}> まもなく開始です！")

                async with bot.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE slots SET notified=true WHERE id=$1",
                        r["id"]
                    )

            except Exception:
                print("❌ per-row error:")
                traceback.print_exc()

    except Exception:
        print("❌ remind_loop crashed:")
        traceback.print_exc()


def start_remind(bot):
    if not remind_loop.is_running():
        remind_loop.start(bot)
        print("✅ remind_loop started")