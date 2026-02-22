from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback
import discord

REMIND_SEC = 180
ALLOW_RANGE = 15

@tasks.loop(seconds=20)
async def remind_loop(bot):
    try:
        now = datetime.now(timezone.utc)
        target_from = now + timedelta(seconds=120)
        target_to   = now + timedelta(seconds=240)

        async with bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.user_id, s.start_at, gs.notify_channel
                FROM slots s
                JOIN guild_settings gs ON gs.guild_id = s.guild_id::text
                WHERE s.start_at >= $1
                  AND s.start_at <  $2
                  AND s.user_id IS NOT NULL
                  AND COALESCE(s.notified,false) = false
                  AND gs.notify_channel IS NOT NULL
                """,
                target_from, target_to
            )

        for r in rows:
            try:
                remaining = (r["start_at"] - now).total_seconds()
                if not (REMIND_SEC - ALLOW_RANGE <= remaining <= REMIND_SEC + ALLOW_RANGE):
                    continue

                ch_id = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(ch_id) or await bot.fetch_channel(ch_id)
                await ch.send(f"<@{user_id}> あと3分であなたの番です！")

                async with bot.pool.acquire() as conn:
                    await conn.execute("UPDATE slots SET notified=true WHERE id=$1", r["id"])

            except (discord.Forbidden, discord.NotFound) as e:
                print("⚠ notify channel error:", e)
            except Exception:
                print("❌ per-row error")
                traceback.print_exc()

    except Exception:
        print("❌ remind_loop crashed (outer)")
        traceback.print_exc()

@remind_loop.error
async def remind_loop_error(exc):
    print("❌ remind_loop stopped by error:", exc)
    traceback.print_exc()

def start_remind(bot):
    if not remind_loop.is_running():
        remind_loop.start(bot)
        print("✅ remind_loop started")