# utils/discord_utils.py
import discord

async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    """
    interaction に対して「二重返信」を絶対に起こさずに送る。
    - まだ response してない → interaction.response.send_message
    - すでに response 済み → interaction.followup.send
    """
    try:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        # ここでさらに落ちないように握りつぶす（ログは必要なら上位で出す）
        pass


async def safe_defer(interaction: discord.Interaction, *, ephemeral: bool = True, thinking: bool = True):
    """
    まだ response してない時だけ defer する（連打・再実行でも安全）
    """
    try:
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=ephemeral, thinking=thinking)
    except Exception:
        pass