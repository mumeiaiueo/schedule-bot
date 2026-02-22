import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))

def setup(bot: discord.Client):

   @bot.tree.command(
    name="create2",
    description="開始/終了/間隔から予約パネル作成 + 通知チャンネル設定（一本化）"
)
    @app_commands.choices(interval=[
        app_commands.Choice(name="20", value=20),
        app_commands.Choice(name="25", value=25),
        app_commands.Choice(name="30", value=30),
    ])
    async def create(
        interaction: discord.Interaction,
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        notify_channel: discord.TextChannel,  # ✅ 必須
    ):
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）", ephemeral=True)
                return

            guild_id_int = interaction.guild.id
            today_jst = datetime.now(JST).date()

            # 日跨ぎ判定
            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            async with bot.pool.acquire() as conn:
                # ✅ 通知チャンネルを保存（一本化）
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

                # このサーバーの枠を作り直し
                await conn.execute("DELETE FROM slots WHERE guild_id = $1", guild_id_int)

                for t in slots:
                    h, m = map(int, t.split(":"))
                    day = today_jst
                    if cross_midnight and (h * 60 + m) < start_min:
                        day = today_jst + timedelta(days=1)

                    start_at_jst = datetime(day.year, day.month, day.day, h, m, tzinfo=JST)
                    start_at_utc = start_at_jst.astimezone(timezone.utc)

                    # slot_time が NOT NULL なので必ず入れる
                    await conn.execute(
                        """
                        INSERT INTO slots (guild_id, slot_time, start_at, user_id, notified)
                        VALUES ($1, $2, $3, NULL, false)
                        """,
                        guild_id_int,
                        t,
                        start_at_utc
                    )

            # パネル表示（今まで通り）
            data = load_data()
            g = get_guild(data, guild_id_int)

            g["slots"] = slots
            g["reservations"] = {}
            g["reminded"] = []
            g["meta"] = {"start_min": start_min, "cross_midnight": cross_midnight}
            save_data(data)

            view = SlotView(guild_id=guild_id_int, page=0)
            msg = await interaction.followup.send(
                content=build_panel_text(g),
                view=view
            )

            g["panel"]["channel_id"] = msg.channel.id
            g["panel"]["message_id"] = msg.id
            save_data(data)

            await interaction.followup.send(
                f"✅ 作成完了：通知チャンネルは {notify_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(f"❌ create失敗: {type(e).__name__}: {e}", ephemeral=True)