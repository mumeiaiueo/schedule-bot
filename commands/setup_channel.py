# commands/setup_channel.py
import discord
from discord import app_commands
from datetime import datetime

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


HOUR_CHOICES = [app_commands.Choice(name=f"{h:02d}", value=h) for h in range(24)]
MIN_CHOICES = [app_commands.Choice(name=f"{m:02d}", value=m) for m in (0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55)]
INTERVAL_CHOICES = [
    app_commands.Choice(name="20分", value=20),
    app_commands.Choice(name="25分", value=25),
    app_commands.Choice(name="30分", value=30),
]


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに予約パネルを作成します（重なり禁止）")
    @app_commands.describe(
        title="募集のタイトル（任意）",
        start_hour="開始（時）",
        start_min="開始（分）",
        end_hour="終了（時）",
        end_min="終了（分）",
        interval="枠の間隔（分）",
        notify_channel="通知を送るチャンネル（3分前通知）※今は一旦ダミーでもOK",
        ping_everyone="募集開始時に @everyone を付ける？（管理者用）",
    )
    @app_commands.choices(
        start_hour=HOUR_CHOICES,
        start_min=MIN_CHOICES,
        end_hour=HOUR_CHOICES,
        end_min=MIN_CHOICES,
        interval=INTERVAL_CHOICES,
    )
    async def setup_channel(
        interaction: discord.Interaction,
        title: str | None,
        start_hour: int,
        start_min: int,
        end_hour: int,
        end_min: int,
        interval: int,
        notify_channel: discord.TextChannel,
        ping_everyone: bool = False,  # ★追加：True/Falseで選べる
    ):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        if notify_channel is None:
            await safe_send(interaction, "❌ notify_channel を選んでね", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            now = jst_now()
            day_date = now.date()

            start_at = datetime(now.year, now.month, now.day, start_hour, start_min, tzinfo=now.tzinfo)
            end_at   = datetime(now.year, now.month, now.day, end_hour, end_min, tzinfo=now.tzinfo)

            if end_at <= start_at:
                await safe_send(interaction, "❌ 終了は開始より後にしてね", ephemeral=True)
                return

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

            # ★募集開始時の @everyone（別メッセージで送る方式）
            if ping_everyone:
                ch = interaction.channel
                if isinstance(ch, discord.TextChannel):
                    me = ch.guild.me
                    can = bool(me and ch.permissions_for(me).mention_everyone)
                    if can:
                        await ch.send(
                            "@everyone 募集パネルを作成しました！下のボタンから予約できます。",
                            allowed_mentions=discord.AllowedMentions(everyone=True)
                        )
                    else:
                        # 権限が無いなら管理者にだけ警告（メンションはしない）
                        await safe_send(
                            interaction,
                            "⚠️ @everyone を付けたいけど、Botに **Mention Everyone** 権限がありません（Discordの招待権限 or チャンネル権限で付与してね）",
                            ephemeral=True,
                        )

            await safe_send(interaction, "✅ パネルを作成しました（ボタンで予約 / もう一度押すとキャンセル）", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @setup_channel.error
    async def setup_channel_error(interaction: discord.Interaction, error: Exception):
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)