from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback
import discord

REMIND_SEC = 180          # 3分前
FETCH_BEFORE = 240        # 4分前まで広く取得（取り逃がし防止）
FETCH_AFTER = 120         # 2分前まで取得
ALLOW_RANGE = 15          # 180秒±15秒のみ送信（ここで精度を決める）

@tasks.loop(seconds=20)
async def remind_loop(bot):
    try:
        now = datetime.now(timezone.utc)

        # 広めに候補取得
        target_from = now + timedelta(seconds=FETCH_AFTER)
        target_to   = now + timedelta(seconds=FETCH_BEFORE)

        async with bot.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.id, s.guild_id, s.user_id, s.start_at, gs.notify_channel
                FROM slots s
                JOIN guild_settings gs ON gs.guild_id = s.guild_id::text
                WHERE s.start_at >= $1
                  AND s.start_at <  $2
                  AND s.user_id IS NOT NULL
                  AND COALESCE(s.notified, false) = false
                  AND gs.notify_channel IS NOT NULL
                """,
                target_from, target_to
            )

        for r in rows:
            try:
                start_at = r["start_at"]
                remaining = (start_at - now).total_seconds()

                # 🎯 ここで「ほぼ3分前だけ」に制限
                if not (REMIND_SEC - ALLOW_RANGE <= remaining <= REMIND_SEC + ALLOW_RANGE):
                    continue

                notify_channel = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(notify_channel)
                if ch is None:
                    ch = await bot.fetch_channel(notify_channel)

                await ch.send(f"<@{user_id}> あと3分であなたの番です！")

                async with bot.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE slots SET notified=true WHERE id=$1",
                        r["id"]
                    )

                print("📣 3分前通知送信:", user_id)

            except Exception:
                print("❌ per-row error")
                traceback.print_exc()

    except Exception:
        print("❌ remind_loop crashed (outer)")
        traceback.print_exc()


def start_remind(bot):
    if not remind_loop.is_running():
        remind_loop.start(bot)
        print("✅ remind_loop started")