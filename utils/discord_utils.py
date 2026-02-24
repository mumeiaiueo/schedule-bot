# utils/discord_utils.py
import discord


async def safe_defer(
    interaction: discord.Interaction,
    *,
    ephemeral: bool = False,
    thinking: bool = False,
):
    """
    すでに応答済みでも落ちない defer。
    """
    try:
        if interaction.response.is_done():
            return
        await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
    except Exception:
        # defer失敗しても落とさない
        return


async def safe_send(
    interaction: discord.Interaction,
    content: str,
    *,
    ephemeral: bool = False,
):
    """
    1回目は response.send_message
    2回目以降は followup.send
    どちらでも失敗しても落ちない
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        # どうしても送れない場合も落とさない
        return