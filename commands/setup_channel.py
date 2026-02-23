import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_channel
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))


def setup(bot: discord.Client):

    @bot.tree.command(
        name="setup_channel",
        description="このチャンネル専用の予約枠を作成（管理者のみ）"
    )
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        title="タイトル（任意）例：夜の部屋",
        day="今日 / 明日",
        start="開始 例 19:00",
        end="終了 例 21:00",
        interval="何分刻み",
        notify_channel="3分前通知を送るチャンネル"
    )
    @app_commands.choices(
        day=[
            app_commands.Choice(name="今日", value="today"),
            app_commands.Choice(name="明日", value="tomorrow"),
        ],
        interval=[
            app_commands.Choice(name="20", value=20),
            app_commands.Choice(name="25", value=25),
            app_commands.Choice(name="30", value=30),
        ]
    )
    async def setup_channel_cmd(
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        notify_channel: discord.TextChannel,
        title: str = ""
    ):
        await interaction.response.defer(thinking=True)

        try:
            # ✅ DB(text)想定：全部 str に統一
            channel_id = str(interaction.channel.id)
            guild_id = str(interaction.guild.id)

            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません", ephemeral=True)
                return

            base_date = datetime.now(JST).date()
            if day.value == "tomorrow":
                base_date += timedelta(days=1)

            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            async with bot.pool.acquire() as conn:

                # チャンネル単位で既存チェック
                exists = await conn.fetchval(
                    "SELECT COUNT(*) FROM slots WHERE channel_id = $1",
                    channel_id
                )
                if exists and exists > 0:
                    await interaction.followup.send(
                        "⚠️ このチャンネルには既に枠があります。\n/reset_channel を実行してください。",
                        ephemeral=True
                    )
                    return

                # 通知設定（チャンネル単位）
                await conn.execute(
                    """
                    INSERT INTO guild_settings (channel_id, guild_id, notify_channel)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (channel_id)
                    DO UPDATE SET notify_channel = EXCLUDED.notify_channel
                    """,
                    channel_id,
                    guild_id,
                    str(notify_channel.id)
                )

                # 枠をDBへ保存
                for t in slots:
                    h, m = map(int, t.split(":"))
                    day_date = base_date
                    if cross_midnight and (h * 60 + m) < start_min:
                        day_date += timedelta(days=1)

                    start_at_jst = datetime(
                        day_date.year, day_date.month, day_date.day, h, m, tzinfo=JST
                    )
                    start_at_utc = start_at_jst.astimezone(timezone.utc)

                       day_date.year, day_date.month, day_date.day, h, m, tzinfo=JST
                    )
                    start_at_utc = start_at_jst.astimezone(timezone.

            # JSON保存（表示用）
            data = load_data()
            c = get_channel(data, channel_id)  # ✅ keyもstrになる

            c["title"] = title.strip()
            c["slots"] = slots
            c["reservations"] = {}
            c["breaks"] = []
            c["meta"] = {
                "start_min": start_min,
                "cross_midnight": cross_midnight,
                "base_date": str(base_date)
            }
            save_data(data)

            # パネル表示
            view = SlotViewChannel(channel_id=channel_id, page=0)
            msg = await interaction.followup.send(
                content=build_panel_text_channel(c),
                view=view
            )

            c.setdefault("panel", {})
            c["panel"]["channel_id"] = str(msg.channel.id)
            c["panel"]["message_id"] = str(msg.id)
            save_data(data)

            await interaction.followup.send(
                f"✅ チャンネル専用枠を作成しました（{day.name}）",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ setup失敗: {type(e).__name__}: {e}",
                ephemeral=True
            )