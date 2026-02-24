import discord
from discord import app_commands
from datetime import datetime, timedelta
import re

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


INTERVAL_CHOICES = [
    app_commands.Choice(name="20分", value=20),
    app_commands.Choice(name="25分", value=25),
    app_commands.Choice(name="30分", value=30),
]

DAY_CHOICES = [
    app_commands.Choice(name="今日", value="today"),
    app_commands.Choice(name="明日", value="tomorrow"),
]


def parse_hm(text: str):
    m = re.match(r"^(\d{1,2}):(\d{2})$", text.strip())
    if not m:
        raise ValueError("時刻は HH:MM 形式で入力してね（例 19:00）")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("時刻が不正です（00:00〜23:59）")
    return hh, mm


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに予約パネルを作成（今日/明日）")
    @app_commands.describe(
        day="今日 or 明日",
        title="募集タイトル（任意）",
        start="開始時刻（例 19:00）",
        end="終了時刻（例 21:00）",
        interval="枠の間隔（20/25/30）",
        notify_channel="通知チャンネル（3分前通知）",
        ping_everyone="募集時に @everyone する？",
    )
    @app_commands.choices(day=DAY_CHOICES, interval=INTERVAL_CHOICES)
    async def setup_channel(
        interaction: discord.Interaction,
        day: str,
        title: str | None,
        start: str,
        end: str,
        interval: int,
        notify_channel: discord.TextChannel,
        ping_everyone: bool = False,
    ):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            now = jst_now()

            base_date = now.date()
            if day == "tomorrow":
                base_date = base_date + timedelta(days=1)

            sh, sm = parse_hm(start)
            eh, em = parse_hm(end)

            start_at = datetime(base_date.year, base_date.month, base_date.day, sh, sm, tzinfo=now.tzinfo)
            end_at   = datetime(base_date.year, base_date.month, base_date.day, eh, em, tzinfo=now.tzinfo)

            # 🌙 日跨ぎ対応（同日入力で end <= start のときは翌日に）
            if end_at <= start_at:
                end_at = end_at + timedelta(days=1)

            # panels.day は「開始日の date」を入れる（今日/明日選択に一致）
            day_date = base_date

            res = await dm.create_panel(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day_date,
                title=title,
                start_at=start_at,
                end_at=end_at,
                interval_minutes=int(interval),
                notify_channel_id=str(notify_channel.id),
                created_by=str(interaction.user.id),
            )

            if not res.get("ok"):
                await safe_send(interaction, f"❌ {res.get('error', '作成に失敗しました')}", ephemeral=True)
                return

            panel_id = res["panel_id"]
            await dm.render_panel(interaction.client, panel_id)

            # 📢 募集時 @everyone（選択式）
            if ping_everyone:
                ch = interaction.channel
                me = ch.guild.me if isinstance(ch, discord.TextChannel) else None
                if me and ch.permissions_for(me).mention_everyone:
                    await ch.send(
                        "@everyone お疲れ様です！お部屋貼れる方いらっしゃいましたらお願い致します🙇",
                        allowed_mentions=discord.AllowedMentions(everyone=True),
                    )
                else:
                    await safe_send(interaction, "⚠️ Botに Mention Everyone 権限がありません", ephemeral=True)

            await safe_send(interaction, "✅ パネル作成完了", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @setup_channel.error
    async def setup_channel_error(interaction: discord.Interaction, error: Exception):
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)