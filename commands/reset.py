import discord
from discord import app_commands

def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset", description="今日/明日の募集を削除（管理者/管理ロールのみ）")
    @app_commands.describe(day="today / tomorrow")
    async def reset_cmd(interaction: discord.Interaction, day: str):
        day = (day or "").strip().lower()
        if day not in ("today", "tomorrow"):
            await interaction.response.send_message("day は today / tomorrow のどちらか", ephemeral=True)
            return

        manager_role_id = await dm.get_manager_role(interaction.guild_id)
        if not dm.is_manager(interaction, manager_role_id):
            await interaction.response.send_message("権限がありません（管理者/管理ロールのみ）", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        await dm.reset_day(interaction.guild_id, day)
        await interaction.followup.send(f"✅ {day} を削除しました", ephemeral=True)