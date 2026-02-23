import discord
from discord import app_commands
from utils.time_utils import jst_today_date

def admin_only(i: discord.Interaction) -> bool:
    return i.user.guild_permissions.administrator

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="remind_channel", description="（管理者）このチャンネルの募集の通知先を変更（今日/明日）")
    @app_commands.check(admin_only)
    @app_commands.choices(day=[
        app_commands.Choice(name="今日", value="today"),
        app_commands.Choice(name="明日", value="tomorrow"),
    ])
    @app_commands.describe(day="今日/明日", notify_channel="通知先チャンネル")
    async def remind_channel(
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
        notify_channel: discord.TextChannel
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or channel is None:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        day_date = jst_today_date(0 if day.value == "today" else 1)

        ok = await dm.update_notify_channel_for_channel_day(
            guild_id=str(guild.id),
            channel_id=str(channel.id),
            day_date=day_date,
            notify_channel_id=str(notify_channel.id),
        )

        await interaction.followup.send(("✅ 更新しました" if ok else "⚠️ このチャンネルに募集がありません"), ephemeral=True)

    @remind_channel.error
    async def remind_channel_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("❌ 管理者のみ実行できます", ephemeral=True)