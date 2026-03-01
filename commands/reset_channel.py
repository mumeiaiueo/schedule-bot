import traceback
import discord
from discord import app_commands
from utils.time_utils import jst_now


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset_channel", description="このチャンネルの今日の募集を削除")
    async def reset_channel(interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            day = jst_now().date()
            ok = await dm.delete_panel_by_channel_day(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day,
            )
            if ok:
                await interaction.followup.send("✅ このチャンネルの募集（今日）を削除しました", ephemeral=True)
            else:
                await interaction.followup.send("ℹ️ 削除対象の募集がありませんでした（今日）", ephemeral=True)

        except Exception:
            print("reset_channel error")
            print(traceback.format_exc())
            try:
                await interaction.followup.send("❌ reset_channel 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass