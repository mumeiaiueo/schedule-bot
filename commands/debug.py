import discord
from discord import app_commands
from utils.data_manager import load_data, get_guild

def setup(bot: discord.Client):

    @bot.tree.command(name="debugdata", description="現在の予約データ確認（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    async def debugdata(interaction: discord.Interaction):
        data = load_data()
        g = get_guild(data, interaction.guild.id)

        lines = [
            f"slots: {len(g['slots'])}",
            f"reservations: {len(g['reservations'])}",
            f"notify_channel: {g.get('notify_channel')}",
            f"panel_message_id: {g.get('panel', {}).get('message_id')}",
        ]

        # 予約の中身（最大20件）
        items = list(g["reservations"].items())[:20]
        lines.append("---- reservations sample ----")
        if items:
            for slot, uid in items:
                lines.append(f"{slot} -> {uid}")
        else:
            lines.append("(empty)")

        await interaction.response.send_message("```" + "\n".join(lines) + "```", ephemeral=True)
