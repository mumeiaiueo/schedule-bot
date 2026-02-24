# commands/notify.py
import discord
from discord import app_commands
from utils.discord_utils import safe_send, safe_defer


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="notify", description="3分前通知を ON/OFF します（自分だけ）")
    @app_commands.describe(mode="on で有効 / off で無効")
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON（有効）", value="on"),
        app_commands.Choice(name="OFF（無効）", value="off"),
    ])
    async def notify(interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await safe_defer(interaction, ephemeral=True)

        enabled = (mode.value == "on")
        await dm.set_notify_enabled(
            guild_id=str(interaction.guild_id),
            user_id=str(interaction.user.id),
            enabled=enabled,
        )

        await safe_send(interaction, f"✅ 3分前通知：{'ON' if enabled else 'OFF'} にしました", ephemeral=True)