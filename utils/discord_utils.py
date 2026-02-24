import discord

async def safe_send(interaction: discord.Interaction, content: str, *, ephemeral: bool = True):
    """
    Interactionに「必ず1回」返信するためのヘルパー。
    - まだ返信してない → response.send_message
    - すでに返信済み → followup.send
    """
    try:
        if interaction.response.is_done():
            return await interaction.followup.send(content, ephemeral=ephemeral)
        else:
            return await interaction.response.send_message(content, ephemeral=ephemeral)
    except Exception:
        # ここで落ちると最悪なので握りつぶし（ログはmain側で出す）
        return None