# commands/break.py
import re
import discord
from discord import app_commands

from utils.time_utils import jst_now
from utils.discord_utils import safe_send, safe_defer


def _is_admin(interaction: discord.Interaction) -> bool:
    m = interaction.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


def _normalize_hm(hm: str) -> str:
    m = re.match(r"^(\d{1,2}):(\d{2})$", hm.strip())
    if not m:
        raise ValueError("時刻は HH:MM で入力してね（例 19:30）")
    hh = int(m.group(1))
    mm = int(m.group(2))
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("時刻が不正です（00:00〜23:59）")
    return f"{hh:02d}:{mm:02d}"


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="break", description="このチャンネルの枠を休憩(予約不可)にする/解除する（管理者）")
    @app_commands.describe(time="休憩にする枠の時刻 (例 19:30)")
    async def break_toggle(interaction: discord.Interaction, time: str):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            slot_time = _normalize_hm(time)
            day_date = jst_now().date()

            ok, msg, panel_id = await dm.toggle_break_by_time(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day_date,
                slot_time=slot_time,
            )

            if panel_id:
                await dm.render_panel(interaction.client, panel_id)

            await safe_send(interaction, msg, ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)