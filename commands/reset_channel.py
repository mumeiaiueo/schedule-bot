import discord
from discord import app_commands

from utils.data_manager import load_data, save_data, get_channel


def setup(bot: discord.Client):

    @bot.tree.command(
        name="reset_channel",
        description="このチャンネルの予約枠を削除（管理者のみ）"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_channel_cmd(interaction: discord.Interaction):

        await interaction.response.defer(ephemeral=True)

        channel_id = interaction.channel.id

        try:
            # DB削除（チャンネル単位）
            async with interaction.client.pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM slots WHERE channel_id = $1",
                    channel_id
                )

            # JSON削除
            data = load_data()
            c = get_channel(data, channel_id)

            c["title"] = ""
            c["slots"] = []
            c["reservations"] = {}
            c["breaks"] = []
            c["meta"] = {}
            c["panel"] = {
                "channel_id": None,
                "message_id": None
            }

            save_data(data)

            await interaction.followup.send(
                "✅ このチャンネルの予約枠を削除しました。\n/setup_channel で再作成できます。",
                ephemeral=True
            )

        except Exception as e:
            await interaction.followup.send(
                f"❌ reset失敗: {type(e).__name__}: {e}",
                ephemeral=True
            )