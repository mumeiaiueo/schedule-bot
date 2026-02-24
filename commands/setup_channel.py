# commands/setup_channel.py
import discord
from discord import app_commands

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer

def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.user:
        return False
    member = interaction.user
    if isinstance(member, discord.Member):
        return member.guild_permissions.administrator
    return False

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに予約パネルを作成します（重なり禁止）")
    @app_commands.describe(
        title="募集のタイトル（任意）",
        start_hm="開始時刻 (例 19:00)",
        end_hm="終了時刻 (例 21:00)",
        interval="枠の間隔（分）(例 20)",
        notify_channel="通知を送るチャンネル（3分前通知）"
    )
    async def setup_channel(
        interaction: discord.Interaction,
        title: str | None,
        start_hm: str,
        end_hm: str,
        interval: int,
        notify_channel: discord.TextChannel,
    ):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            now = jst_now()
            day_date = now.date()

            # 時刻パースは time_utils 側に寄せる想定が多いけど、
            # ここでは dm.create_panel が start_at/end_at を datetime で受ける前提のまま。
            # あなたの time_utils に合わせて parse 関数があるならそこに差し替えてOK。
            from datetime import datetime
            import re

            def parse_hm(hm: str):
                m = re.match(r"^(\d{1,2}):(\d{2})$", hm.strip())
                if not m:
                    raise ValueError("時刻は HH:MM で入力してね（例 19:00）")
                hh = int(m.group(1))
                mm = int(m.group(2))
                return hh, mm

            sh, sm = parse_hm(start_hm)
            eh, em = parse_hm(end_hm)

            start_at = datetime(now.year, now.month, now.day, sh, sm, tzinfo=now.tzinfo)
            end_at   = datetime(now.year, now.month, now.day, eh, em, tzinfo=now.tzinfo)

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
                await safe_send(interaction, f"❌ {res.get('error','作成に失敗しました')}", ephemeral=True)
                return

            panel_id = res["panel_id"]
            await dm.render_panel(interaction.client, panel_id)

            await safe_send(interaction, "✅ パネルを作成しました（ボタンで予約/もう一度押すとキャンセル）", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @setup_channel.error
    async def setup_channel_error(interaction: discord.Interaction, error: Exception):
        # ★ここが二重返信の根源だったので safe_send に統一
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)