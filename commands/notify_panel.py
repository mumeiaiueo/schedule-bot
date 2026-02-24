import discord
from discord import app_commands
from utils.discord_utils import safe_send, safe_defer
from utils.time_utils import jst_now


def _is_admin(i: discord.Interaction) -> bool:
    m = i.user
    return isinstance(m, discord.Member) and m.guild_permissions.administrator


def register(tree: app_commands.CommandTree, dm):

    @tree.command(
        name="notify_panel",
        description="このチャンネルの今日の3分前通知を管理（管理者）"
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON（有効）", value="on"),
        app_commands.Choice(name="OFF（無効）", value="off"),
        app_commands.Choice(name="PAUSE（一時停止）", value="pause"),
        app_commands.Choice(name="RESUME（一時停止解除）", value="resume"),
    ])
    async def notify_panel(
        interaction: discord.Interaction,
        mode: app_commands.Choice[str]
    ):
        if not _is_admin(interaction):
            await safe_send(interaction, "❌ 管理者のみ実行できます", ephemeral=True)
            return

        await safe_defer(interaction, ephemeral=True, thinking=True)

        day_date = jst_now().date()

        ok, msg = await dm.set_panel_notify_state(
            guild_id=str(interaction.guild_id),
            channel_id=str(interaction.channel_id),
            day_date=day_date,
            mode=mode.value,
        )

        await safe_send(
            interaction,
            msg if ok else f"❌ {msg}",
            ephemeral=True
        )