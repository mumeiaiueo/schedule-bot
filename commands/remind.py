from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback
import discord

# 何秒前に送るか
REMIND_SEC = 180
# 取り逃し防止の許容幅（例：±90秒）
WINDOW_SEC = 90

@tasks.loop(seconds=20)
async def remind_loop(bot):
    try:
        now = datetime.now(timezone.utc)

        # “だいたい3分前”の範囲（広め）
        target_from = now + timedelta(seconds=REMIND_SEC - WINDOW_SEC)
        target_to   = now + timedelta(seconds=REMIND_SEC + WINDOW_SEC)

        async with bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.guild_id, s.user_id, s.start_at, gs.notify_channel, COALESCE(s.notified,false) AS notified
                FROM slots s
                JOIN guild_settings gs ON gs.guild_id = s.guild_id::text
                WHERE s.start_at >= $1
                  AND s.start_at <  $2
                  AND COALESCE(s.notified, false) = false
                  AND gs.notify_channel IS NOT NULL
                  AND s.user_id IS NOT NULL
                """,
                target_from, target_to
            )

        print("🔎 remind candidates:", len(rows))

        for r in rows:
            try:
                start_at = r["start_at"]  # timestamptz
                remaining = (start_at - now).total_seconds()

                # 念のため、秒数でもう一段フィルタ（変な一致を防ぐ）
                if not (REMIND_SEC - WINDOW_SEC <= remaining < REMIND_SEC + WINDOW_SEC):
                    continue

                notify_channel = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(notify_channel)
                if ch is None:
                    ch = await bot.fetch_channel(notify_channel)

                await ch.send(f"<@{user_id}> もうすぐあなたの番です！")

                async with bot.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE slots SET notified=true WHERE id=$1",
                        r["id"]
                    )

            except (discord.Forbidden, discord.NotFound) as e:
                print("⚠ channel access error:", e, "channel_id=", r.get("notify_channel"))
            except Exception:
                print("❌ per-row error:", dict(r))
                traceback.print_exc()

    except Exception:
        print("❌ remind_loop crashed:")
        traceback.print_exc()

def start_remind(bot):
    if not remind_loop.is_running():
        remind_loop.start(bot)
        print("✅ remind_loop started")