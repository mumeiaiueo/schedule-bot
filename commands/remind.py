from discord.ext import tasks
from datetime import datetime, timedelta, timezone
import traceback
import discord

@tasks.loop(seconds=20)
async def remind_loop(bot):
    try:
        now = datetime.now(timezone.utc)

        # テスト窓（今-1分〜今+10分）
target_from = now + timedelta(minutes=3)
target_to   = now + timedelta(minutes=3, seconds=20)

        print("⏱ now(UTC):", now.isoformat())
        print("⏱ window:", target_from.isoformat(), " -> ", target_to.isoformat())

        async with bot.pool.acquire() as conn:
            # ① slotsにそもそもデータがあるか（全体）
            total_slots = await conn.fetchval("SELECT COUNT(*) FROM slots")
            print("📦 slots total:", total_slots)

            # ② このギルドのslots件数
            guild_id_guess = None
            # guild_id が bigint/text どっちでも対応できるように、両方試す
            try:
                guild_id_guess = int(getattr(bot, "last_guild_id", 0) or 0)
            except:
                guild_id_guess = 0

            # last_guild_id が無い場合は、guild_settings から1つ拾う
            if not guild_id_guess:
                gid = await conn.fetchval("SELECT guild_id FROM guild_settings LIMIT 1")
                try:
                    guild_id_guess = int(gid)
                except:
                    guild_id_guess = 0

            if guild_id_guess:
                guild_slots = await conn.fetchval(
                    "SELECT COUNT(*) FROM slots WHERE guild_id::text = $1",
                    str(guild_id_guess)
                )
                print("🏠 slots for guild:", guild_id_guess, "count:", guild_slots)

                # ③ このギルドで窓に入るstart_at件数（JOIN無し）
                range_slots = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM slots
                    WHERE guild_id::text = $3
                      AND start_at >= $1
                      AND start_at <  $2
                    """,
                    target_from, target_to, str(guild_id_guess)
                )
                print("⏰ slots in window (no join):", range_slots)

                # ④ start_atのサンプル（上位5件）
                sample = await conn.fetch(
                    """
                    SELECT id, guild_id, slot_time, start_at, user_id, notified
                    FROM slots
                    WHERE guild_id::text = $1
                    ORDER BY start_at ASC
                    LIMIT 5
                    """,
                    str(guild_id_guess)
                )
                if sample:
                    print("🔎 sample slots (first 5):")
                    for r in sample:
                        print("  ", dict(r))
                else:
                    print("🔎 sample slots: none for this guild")

            # ⑤ ここから本来の候補（JOINあり）
            rows = await conn.fetch(
                """
                SELECT s.id, s.guild_id, s.user_id, s.start_at, gs.notify_channel
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
        if rows:
            print("🔎 sample candidate:", dict(rows[0]))

        for r in rows:
            try:
                notify_channel = int(r["notify_channel"])
                user_id = int(r["user_id"])

                ch = bot.get_channel(notify_channel)
                if ch is None:
                    ch = await bot.fetch_channel(notify_channel)

                await ch.send(f"<@{user_id}> まもなく開始です！（start_at={r['start_at']}）")

                async with bot.pool.acquire() as conn:
                    await conn.execute("UPDATE slots SET notified=true WHERE id=$1", r["id"])

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