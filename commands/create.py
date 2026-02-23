import discord
from discord import app_commands
from datetime import datetime, timedelta, timezone

from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

JST = timezone(timedelta(hours=9))


def setup(bot: discord.Client):

    # =============================
    # /setup2（管理者のみ・上書き防止）
    # =============================
    @bot.tree.command(name="setup2", description="枠作成 + 通知設定（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.describe(
        title="タイトル（任意）例：夜の部屋",
        day="今日/明日",
        start="開始 例 19:00",
        end="終了 例 21:00",
        notify_channel="3分前通知を送るチャンネル",
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
        day: app_commands.Choice[str],
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        notify_channel: discord.TextChannel,
        title: str = "",
    ):
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）", ephemeral=True)
                return

            guild_id = interaction.guild.id

            # 今日 / 明日
            base_date = datetime.now(JST).date()
            if day.value == "tomorrow":
                base_date = base_date + timedelta(days=1)

            # 日跨ぎ判定
            start_h, start_m = map(int, start.split(":"))
            end_h, end_m = map(int, end.split(":"))
            start_min = start_h * 60 + start_m
            end_min = end_h * 60 + end_m
            cross_midnight = end_min <= start_min

            async with bot.pool.acquire() as conn:

                # ✅ 上書き防止：既に枠があるなら止める
                existing = await conn.fetchval(
                    "SELECT COUNT(*) FROM slots WHERE guild_id = $1",
                    guild_id
                )
                if existing and existing > 0:
                    await interaction.followup.send(
                        "⚠️ 既に枠が存在します。\n"
                        "上書きしたい場合は **/reset** を実行してからもう一度 **/setup2** してください。",
                        ephemeral=True
                    )
                    return

                # ✅ 通知チャンネル保存
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

                # ✅ 枠をDBに作成
                for t in slots:
                    h, m = map(int, t.split(":"))
                    day_date = base_date

                    if cross_midnight and (h * 60 + m) < start_min:
                        day_date = base_date + timedelta(days=1)

                    start_at_jst = datetime(
                        day_date.year, day_date.month, day_date.day, h, m, tzinfo=JST
                    )
                    start_at_utc = start_at_jst.astimezone(timezone.utc)

                    await conn.execute(
                        """
                        INSERT INTO slots (guild_id, slot_time, start_at, user_id, notified, is_break)
                        VALUES ($1, $2, $3, NULL, false, false)
                        """,
                        guild_id,
                        t,
                        start_at_utc
                    )

            # ✅ JSON（表示用）更新
            data = load_data()
            g = get_guild(data, guild_id)

            g["title"] = (title or "").strip()
            g["slots"] = slots
            g["reservations"] = {}
            g["breaks"] = []
            g["meta"] = {
                "start_min": start_min,
                "cross_midnight": cross_midnight,
                "base_date": str(base_date),
            }
            save_data(data)

            # ✅ パネル投稿
            view = SlotView(guild_id=guild_id, page=0)
            msg = await interaction.followup.send(
                content=build_panel_text(g),
                view=view
            )

            # ✅ パネル位置保存（休憩切替などの即時更新に使う）
            g["panel"]["channel_id"] = msg.channel.id
            g["panel"]["message_id"] = msg.id
            save_data(data)

            # ✅ 完了メッセージ
            title_txt = f"" if g["title"] else ""
            await interaction.followup.send(
                f"✅ セットアップ完了 {title_txt}（{day.name}）\n通知: {notify_channel.mention}",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ setup失敗: {type(e).__name__}: {e}",
                ephemeral=True
            )

    # =============================
    # /reset（管理者のみ・明示的に削除）
    # =============================
    @bot.tree.command(name="reset", description="既存の枠を削除（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # DB削除
        async with bot.pool.acquire() as conn:
            await conn.execute("DELETE FROM slots WHERE guild_id = $1", interaction.guild.id)

        # JSONもリセット
        data = load_data()
        g = get_guild(data, interaction.guild.id)
        g["slots"] = []
        g["reservations"] = {}
        g["breaks"] = []
        g["title"] = g.get("title", "")
        save_data(data)

        await interaction.followup.send("✅ 枠をリセットしました（/setup2 で作り直せます）", ephemeral=True)