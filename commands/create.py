import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))


def setup(bot: discord.Client):

    @bot.tree.command(name="setup2", description="枠作成 + 通知設定")
    @app_commands.describe(
        title="タイトル（例：夜の部屋）",
        start="開始 例 19:00",
        end="終了 例 21:00",
        notify_channel="通知チャンネル",
        day="今日 or 明日",
    )
    @app_commands.choices(
        interval=[
            app_commands.Choice(name="20", value=20),
            app_commands.Choice(name="25", value=25),
            app_commands.Choice(name="30", value=30),
        ],
        day=[
            app_commands.Choice(name="今日", value="today"),
            app_commands.Choice(name="明日", value="tomorrow"),
        ],
    )
    async def setup_cmd(
        interaction: discord.Interaction,
        title: str,
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        notify_channel: discord.TextChannel,
        day: app_commands.Choice[str],
    ):
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません", ephemeral=True)
                return

            guild_id = interaction.guild.id

            # 今日 / 明日 判定
            today = datetime.now(JST).date()
            if day.value == "tomorrow":
                base_date = today + timedelta(days=1)
            else:
                base_date = today

            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))

            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            async with bot.pool.acquire() as conn:

                # 通知チャンネル保存
                await conn.execute(
                    """
                    INSERT INTO guild_settings (guild_id, notify_channel)
                    VALUES ($1, $2)
                    ON CONFLICT (guild_id)
                    DO UPDATE SET notify_channel = EXCLUDED.notify_channel
                    """,
                    str(guild_id),
                    str(notify_channel.id)
                )

                # 既存削除
                await conn.execute(
                    "DELETE FROM slots WHERE guild_id = $1",
                    guild_id
                )

                # 枠作成
                for t in slots:
                    h, m = map(int, t.split(":"))
                    day_date = base_date

                    if cross_midnight and (h * 60 + m) < start_min:
                        day_date = base_date + timedelta(days=1)

                    start_at_jst = datetime(
                        day_date.year,
                        day_date.month,
                        day_date.day,
                        h,
                        m,
                        tzinfo=JST
                    )

                    await conn.execute(
                        """
                        INSERT INTO slots (guild_id, slot_time, start_at, user_id, notified)
                        VALUES ($1, $2, $3, NULL, false)
                        """,
                        guild_id,
                        t,
                        start_at_jst.astimezone(timezone.utc)
                    )

            # JSON保存
            data = load_data()
            g = get_guild(data, guild_id)

            g["title"] = title
            g["slots"] = slots
            g["reservations"] = {}
            g["breaks"] = []
            g["meta"] = {
                "start_min": start_min,
                "cross_midnight": cross_midnight,
                "base_date": str(base_date),
            }

            save_data(data)

            view = SlotView(guild_id, page=0)
            msg = await interaction.followup.send(
                content=build_panel_text(g),
                view=view
            )

            g["panel"] = {
                "channel_id": msg.channel.id,
                "message_id": msg.id,
            }
            save_data(data)

            await interaction.followup.send(
                "✅ セットアップ完了",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ setup失敗: {type(e).__name__}: {e}",
                ephemeral=True
            )