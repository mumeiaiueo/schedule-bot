import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))

def setup(bot: discord.Client):

    @bot.tree.command(name="create", description="開始/終了と間隔から予約パネルを作成")
    @app_commands.describe(start="開始 例 18:00", end="終了 例 01:00")
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
    ):
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）", ephemeral=True)
                return

            # ===== ここからDBにも枠を作る =====
            guild_id_int = interaction.guild.id  # slots.guild_id は BIGINT 想定
            today_jst = datetime.now(JST).date()

            # 日跨ぎ判定
            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            # いったんこのサーバーの枠を全削除（運用に合わせて調整可）
            async with bot.pool.acquire() as conn:
                await conn.execute("DELETE FROM slots WHERE guild_id = $1", guild_id_int)

                # 枠INSERT（user_idはNULL、notified=false）
                for t in slots:
                    h, m = map(int, t.split(":"))
                    day = today_jst
                    if cross_midnight:
                        # startより小さい時刻は翌日扱い
                        if (h * 60 + m) < start_min:
                            day = today_jst + timedelta(days=1)

                    start_at_jst = datetime(day.year, day.month, day.day, h, m, tzinfo=JST)
                    start_at_utc = start_at_jst.astimezone(timezone.utc)

                    await conn.execute(
                        """
                        INSERT INTO slots (guild_id, start_at, user_id, notified)
                        VALUES ($1, $2, NULL, false)
                        """,
                        guild_id_int,
                        start_at_utc
                    )
            # ===== DB枠作成ここまで =====

            # 既存のパネル表示ロジック（今まで通り）
            data = load_data()
            g = get_guild(data, interaction.guild.id)

            g["slots"] = slots
            g["reservations"] = {}
            g["reminded"] = []
            g["meta"] = {"start_min": start_min, "cross_midnight": cross_midnight}
            save_data(data)

            view = SlotView(guild_id=interaction.guild.id, page=0)
            msg = await interaction.followup.send(content=build_panel_text(g), view=view)

            g["panel"]["channel_id"] = msg.channel.id
            g["panel"]["message_id"] = msg.id
            save_data(data)

        except Exception as e:
            await interaction.followup.send(f"❌ create失敗: {type(e).__name__}: {e}", ephemeral=True)