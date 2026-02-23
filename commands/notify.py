import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="notify", description="（ユーザー）通知ON/OFF/状態")
    @app_commands.choices(mode=[
        app_commands.Choice(name="ON", value="on"),
        app_commands.Choice(name="OFF", value="off"),
        app_commands.Choice(name="STATUS", value="status"),
    ])
    async def notify(interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("❌ サーバー内で実行してください", ephemeral=True)
            return

        gid = str(guild.id)
        uid = str(interaction.user.id)

        if mode.value == "status":
            enabled = await dm.get_notify_enabled(gid, uid)
            await interaction.followup.send(f"🔔 通知：{'ON' if enabled else 'OFF'}", ephemeral=True)
            return

        enabled = (mode.value == "on")
        await dm.set_notify_enabled(gid, uid, enabled)
        await interaction.followup.send(f"✅ 通知を {'ON' if enabled else 'OFF'} にしました", ephemeral=True)