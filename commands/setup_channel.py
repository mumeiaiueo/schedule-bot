import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))


def setup(bot: discord.Client):

    @bot.tree.command(
        name="setup_channel",
        description="このチャンネル専用の予約枠を作成（管理者のみ）"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_channel_cmd(
        interaction: discord.Interaction,
        start: str,
        end: str,
        interval: int
    ):
        await interaction.response.defer(thinking=True)

        try:
            guild_id = interaction.guild.id
            channel_id = interaction.channel.id

            slots = generate_slots(start, end, interval)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません", ephemeral=True)
                return

            base_date = datetime.now(JST).date()

            async with bot.pool.acquire() as conn:

                await conn.execute(
                    "DELETE FROM slots WHERE channel_id = $1",
                    channel_id
                )

                for t in slots:
                    h, m = map(int, t.split(":"))

                    start_at = datetime(
                        base_date.year,
                        base_date.month,
                        base_date.day,
                        h,
                        m,
                        tzinfo=JST
                    )

                    await conn.execute(
                        """
                        INSERT INTO slots
                        (guild_id, channel_id, slot_time, start_at, user_id, notified, is_break)
                        VALUES ($1,$2,$3,$4,NULL,false,false)
                        """,
                        guild_id,
                        channel_id,
                        t,
                        start_at.astimezone(timezone.utc)
                    )

            view = SlotView(channel_id)
            await interaction.followup.send(
                content="✅ 予約パネルを作成しました",
                view=view
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ setup失敗: {type(e).__name__}: {e}",
                ephemeral=True
            )