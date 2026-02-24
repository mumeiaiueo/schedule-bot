# commands/setup_channel.py
import discord
from discord import app_commands

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer


def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.user:
        return False
    member = interaction.user
    return isinstance(member, discord.Member) and member.guild_permissions.administrator


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに予約パネルを作成します（重なり禁止）")
    @app_commands.describe(
        title="募集のタイトル（任意）",
        start_hm="開始時刻 (例 19:00)",
        end_hm="終了時刻 (例 21:00)",
        interval="枠の間隔（分）(例 20)",
        notify_channel="通知を送るチャンネル（3分前通知）",
    )
    async def setup_channel(
        interaction: discord.Interaction,
        title: str = None,  # ★安全のため str|None ではなくこれ
        start_hm: str = "19:00",
        end_hm: str = "21:00",
        interval: int = 20,
        notify_channel: discord.TextChannel = None,
    ):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        if notify_channel is None:
            await safe_send(interaction, "❌ notify_channel が選択されていません", ephemeral=True)
            return

        # 3秒制限対策：先にdefer
        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            now = jst_now()
            day_date = now.date()

            from datetime import datetime
            import re

            def parse_hm(hm: str):
                m = re.match(r"^(\d{1,2}):(\d{2})$", hm.strip())
                if not m:
                    raise ValueError("時刻は HH:MM で入力してね（例 19:00）")
                hh = int(m.group(1))
                mm = int(m.group(2))
                if not (0 <= hh <= 23 and 0 <= mm <= 59):
                    raise ValueError("時刻が不正です（00:00〜23:59）")
                return hh, mm

            sh, sm = parse_hm(start_hm)
            eh, em = parse_hm(end_hm)

            start_at = datetime(now.year, now.month, now.day, sh, sm, tzinfo=now.tzinfo)
            end_at = datetime(now.year, now.month, now.day, eh, em, tzinfo=now.tzinfo)

            if end_at <= start_at:
                await safe_send(interaction, "❌ 終了時刻は開始時刻より後にしてね", ephemeral=True)
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
                await safe_send(
                    interaction,
                    f"❌ {res.get('error', '作成に失敗しました')}",
                    ephemeral=True,
                )
                return

            panel_id = res["panel_id"]
            await dm.render_panel(interaction.client, panel_id)

            await safe_send(
                interaction,
                "✅ パネルを作成しました（ボタンで予約 / もう一度押すとキャンセル）",
                ephemeral=True,
            )

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @setup_channel.error
    async def setup_channel_error(interaction: discord.Interaction, error: Exception):
        # 二重返信防止：safe_sendで統一
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)