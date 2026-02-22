import discord
from discord import app_commands

def setup(bot: discord.Client):

    @bot.tree.command(name="notifyset", description="3分前通知を送るチャンネルを設定（管理者のみ）")
    @app_commands.checks.has_permissions(administrator=True)
    async def notifyset(interaction: discord.Interaction, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        guild_id = str(interaction.guild.id)
        ch_id = str(channel.id)  # ⭐ int → str に変更

        async with bot.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO guild_settings (guild_id, notify_channel)
                VALUES ($1, $2)
                ON CONFLICT (guild_id)
                DO UPDATE SET notify_channel = EXCLUDED.notify_channel
                """,
                guild_id,
                ch_id
            )

        await interaction.followup.send(f"✅ 通知チャンネルを {channel.mention} に設定しました", ephemeral=True)
