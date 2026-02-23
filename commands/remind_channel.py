from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback

REMIND_SEC = 180          # 3分前
FETCH_BEFORE = 240        # 4分前まで広く取得
FETCH_AFTER = 120         # 2分前まで取得
ALLOW_RANGE = 20          # ±20秒許容

@tasks.loop(seconds=20)
async def remind_loop_channel(bot):

    try:
        now = datetime.now(timezone.utc)

        target_from = now + timedelta(seconds=FETCH_AFTER)
        target_to   = now + timedelta(seconds=FETCH_BEFORE)

        async with bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id,
                       s.channel_id,
                       s.user_id,
                       s.start_at,
                       gs.notify_channel
                FROM slots s
                JOIN guild_settings gs
                  ON gs.channel_id = s.channel_id
                WHERE s.start_at >= $1
                  AND s.start_at <  $2
                  AND s.user_id IS NOT NULL
                  AND COALESCE(s.notified,false) = false
                  AND gs.notify_channel IS NOT NULL
                """,
                target_from,
                target_to
            )

        for r in rows:
            try:
                remaining = (r["start_at"] - now).total_seconds()

                if not (REMIND_SEC - ALLOW_RANGE <= remaining <= REMIND_SEC + ALLOW_RANGE):
                    continue

                notify_channel_id = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(notify_channel_id)
                if ch is None:
                    ch = await bot.fetch_channel(notify_channel_id)

                await ch.send(f"<@{user_id}> もうすぐあなたの番です！")

                async with bot.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE slots SET notified=true WHERE id=$1",
                        r["id"]
                    )

                print("📣 通知送信:", user_id)

            except Exception:
                print("❌ per-row error")
                traceback.print_exc()

    except Exception:
        print("❌ remind_loop_channel crashed")
        traceback.print_exc()


def start_remind_channel(bot):
    if not remind_loop_channel.is_running():
        remind_loop_channel.start(bot)
        print("✅ remind_loop_channel started")