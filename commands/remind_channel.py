# commands/remind_channel.py
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
    @tree.command(name="remind_channel", description="このチャンネルの募集の通知先チャンネルを変更します")
    @app_commands.describe(notify_channel="3分前通知を送るチャンネル")
    async def remind_channel(interaction: discord.Interaction, notify_channel: discord.TextChannel):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            day_date = jst_now().date()
            ok = await dm.update_notify_channel_for_channel_day(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day_date,
                notify_channel_id=str(notify_channel.id),
            )
            if ok:
                await safe_send(interaction, f"✅ 通知チャンネルを {notify_channel.mention} に設定しました", ephemeral=True)
            else:
                await safe_send(interaction, "⚠️ 変更対象の募集が見つかりませんでした（先に /setup_channel してね）", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @remind_channel.error
    async def remind_channel_error(interaction: discord.Interaction, error: Exception):
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)