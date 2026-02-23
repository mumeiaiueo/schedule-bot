import discord
from discord import app_commands

from utils.time_utils import jst_today_date, parse_hm, build_range_jst

DAY_CHOICES = [
    app_commands.Choice(name="今日", value="today"),
    app_commands.Choice(name="明日", value="tomorrow"),
]

INTERVAL_CHOICES = [
    app_commands.Choice(name="20分", value=20),
    app_commands.Choice(name="25分", value=25),
    app_commands.Choice(name="30分", value=30),
]

def admin_only(i: discord.Interaction) -> bool:
    return i.user.guild_permissions.administrator

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="（管理者）このチャンネルに募集パネルを作る（重なり不可）")
    @app_commands.check(admin_only)
    @app_commands.choices(day=DAY_CHOICES, interval=INTERVAL_CHOICES)
    @app_commands.describe(
        day="今日 or 明日",
        start="開始 (例 19:00)",
        end="終了 (例 21:00 / 24:00もOK)",
        interval="間隔",
        title="任意タイトル",
        notify_channel="通知先（省略でこのチャンネル）"
    )
    async def setup_channel(
        interaction: discord.Interaction,
        day: app_commands.Choice[str],
        start: str,
        end: str,
        interval: app_commands.Choice[int],
        title: str = None,
        notify_channel: discord.TextChannel = None,
    ):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        channel = interaction.channel
        if guild is None or channel is None:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        day_date = jst_today_date(0 if day.value == "today" else 1)
        sh, sm = parse_hm(start)
        eh, em = parse_hm(end)
        start_dt, end_dt = build_range_jst(day_date, sh, sm, eh, em)

        notify_ch = notify_channel or channel

        res = await dm.create_panel(
            guild_id=str(guild.id),
            channel_id=str(channel.id),
            day_date=day_date,
            title=title,
            start_at=start_dt,
            end_at=end_dt,
            interval_minutes=interval.value,
            notify_channel_id=str(notify_ch.id),
            created_by=str(interaction.user.id),
        )

        if not res["ok"]:
            await interaction.followup.send(f"❌ {res['error']}", ephemeral=True)
            return

        panel_id = res["panel_id"]
        await dm.render_panel(interaction.client, panel_id)
        await interaction.followup.send("✅ 募集パネルを作成しました", ephemeral=True)

    @setup_channel.error
    async def setup_channel_error(interaction: discord.Interaction, error):
        await interaction.response.send_message("❌ 管理者のみ実行できます", ephemeral=True)