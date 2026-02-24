# commands/notify.py
import discord
from discord import app_commands

from utils.discord_utils import safe_send, safe_defer

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="notify", description="3分前通知を ON/OFF します（自分用）")
    @app_commands.describe(mode="on で通知ON / off で通知OFF")
    async def notify(interaction: discord.Interaction, mode: str):
        await safe_defer(interaction, ephemeral=True, thinking=True)

        try:
            mode2 = (mode or "").strip().lower()
            if mode2 not in ("on", "off"):
                await safe_send(interaction, "❌ mode は on か off で指定してね（例: /notify on）", ephemeral=True)
                return

            enabled = (mode2 == "on")
            await dm.set_notify_enabled(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                enabled=enabled,
            )
            await safe_send(interaction, f"✅ 3分前通知を {'ON' if enabled else 'OFF'} にしました", ephemeral=True)

        except Exception as e:
            await safe_send(interaction, f"❌ エラー: {repr(e)}", ephemeral=True)

    @notify.error
    async def notify_error(interaction: discord.Interaction, error: Exception):
        await safe_send(interaction, f"❌ エラー: {error}", ephemeral=True)