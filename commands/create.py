import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone, date as dt_date

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))

def resolve_base_date(date_arg: str | None) -> dt_date:
    """today / tomorrow / YYYY-MM-DD をJST基準日(date)に変換"""
    today = datetime.now(JST).date()
    s = (date_arg or "today").strip().lower()

    if s in ("today", "今日"):
        return today
    if s in ("tomorrow", "明日"):
        return today + timedelta(days=1)

    # YYYY-MM-DD
    y, m, d = map(int, s.split("-"))
    return dt_date(y, m, d)


def setup(bot: discord.Client):

    @bot.tree.command(name="setup2", description="枠作成 + 通知設定（一本化）")
    @app_commands.describe(
        start="開始 例 07:30",
        end="終了 例 08:30",
        notify_channel="3分前通知を送るチャンネル",
        date="基準日: today / tomorrow / YYYY-MM-DD（例: 2026-02-24）",
    )
    @app_commands.choices(interval=[
        app_commands.Choice(name="20", value=20),
        app_commands.Choice(name="25", value=25),
        app_commands.Choice(name="30", value=30),
    ])
    async def setup_cmd(
        interaction: discord.Interaction,
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        notify_channel: discord.TextChannel,
        date: str = "today",
    ):
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）", ephemeral=True)
                return

            guild_id_int = interaction.guild.id
            base_date = resolve_base_date(date)  # ✅ ここが追加
            today_jst = base_date               # 以降のロジックはそのまま

            # 日跨ぎ判定
            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            async with bot.pool.acquire() as conn:
                # ✅ 通知チャンネル保存（一本化）
                await conn.execute(
                    """
                    INSERT INTO guild_settings (guild_id, notify_channel)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET notify_channel = EXCLUDED.notify_channel
                    """,
                    str(guild_id_int),
                    str(notify_channel.id)
                )

                # 既存枠削除 → 作り直し
                await conn.execute("DELETE FROM slots WHERE guild_id = $1", guild_id_int)

                for t in slots:
                    h, m = map(int, t.split(":"))
                    day = today_jst
                    if cross_midnight and (h * 60 + m) < start_min:
                        day = today_jst + timedelta(days=1)

                    start_at_jst = datetime(day.year, day.month, day.day, h, m, tzinfo=JST)
                    start_at_utc = start_at_jst.astimezone(timezone.utc)

                    await conn.execute(
                        """
                        INSERT INTO slots (guild_id, slot_time, start_at, user_id, notified)
                        VALUES ($1, $2, $3, NULL, false)
                        """,
                        guild_id_int,
                        t,
                        start_at_utc
                    )

            # パネル表示（従来通り）
            data = load_data()
            g = get_guild(data, guild_id_int)

            g["slots"] = slots
            g["reservations"] = {}
            g["reminded"] = []
            g["meta"] = {"start_min": start_min, "cross_midnight": cross_midnight, "base_date": str(today_jst)}
            save_data(data)

            view = SlotView(guild_id=guild_id_int, page=0)
            msg = await interaction.followup.send(content=build_panel_text(g), view=view)

            g["panel"]["channel_id"] = msg.channel.id
            g["panel"]["message_id"] = msg.id
            save_data(data)

            await interaction.followup.send(
                f"✅ セットアップ完了（基準日: {today_jst} JST）：通知チャンネルは {notify_channel.mention}",
                ephemeral=True
            )

        except ValueError:
            await interaction.followup.send("❌ date は today / tomorrow / YYYY-MM-DD の形式で入力してください", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ setup失敗: {type(e).__name__}: {e}", ephemeral=True)