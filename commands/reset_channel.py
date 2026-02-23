import discord
from discord import app_commands
from utils.time_utils import jst_today_date

def admin_only(i: discord.Interaction) -> bool:
    return i.user.guild_permissions.administrator

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset_channel", description="（管理者）このチャンネルの募集を削除（今日/明日）")
    @app_commands.check(admin_only)
    @app_commands.choices(day=[
        app_commands.Choice(name="今日", value="today"),
        app_commands.Choice(name="明日", value="tomorrow"),
    ])
    async def reset_channel(interaction: discord.Interaction, day: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or channel is None:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        day_date = jst_today_date(0 if day.value == "today" else 1)

        ok = await dm.delete_panel_by_channel_day(
            guild_id=str(guild.id),
            channel_id=str(channel.id),
            day_date=day_date,
        )

        await interaction.followup.send(("✅ 削除しました" if ok else "⚠️ 削除対象がありません"), ephemeral=True)

    @reset_channel.error
    async def reset_channel_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("❌ 管理者のみ実行できます", ephemeral=True)