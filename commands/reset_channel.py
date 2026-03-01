# commands/reset_channel.py
import traceback
import discord
from discord import app_commands
from utils.time_utils import jst_now


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset_channel", description="このチャンネルの募集（今日/明日）を削除")
    @app_commands.describe(day="today か tomorrow")
    async def reset_channel(interaction: discord.Interaction, day: str = "today"):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            # 管理者/管理ロールのみ
            if not await dm.is_manager(interaction):
                await interaction.followup.send("❌ 管理者/管理ロールのみ実行できます", ephemeral=True)
                return

            now = jst_now()
            if day == "tomorrow":
                day_date = (now + __import__("datetime").timedelta(days=1)).date()
            else:
                day_date = now.date()

            ok = await dm.delete_panel_by_channel_day(
                guild_id=str(interaction.guild_id),
                channel_id=str(interaction.channel_id),
                day_date=day_date,
            )

            if ok:
                await interaction.followup.send(f"✅ このチャンネルの募集（{day_date}）を削除しました", ephemeral=True)
            else:
                await interaction.followup.send("⚠ 削除対象の募集が見つかりませんでした", ephemeral=True)

        except Exception:
            print("❌ reset_channel error")
            print(traceback.format_exc())
            try:
                await interaction.followup.send("❌ reset_channel 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass