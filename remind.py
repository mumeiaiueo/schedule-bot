import discord
from discord import app_commands
import json
import os

DATA="data/remind.json"

def save(cid):
    os.makedirs("data",exist_ok=True)
    with open(DATA,"w") as f:
        json.dump({"cid":cid},f)

def setup(bot):

    @bot.tree.command(name="setremind")
    async def setremind(interaction:discord.Interaction,channel:discord.TextChannel):
        save(channel.id)
        await interaction.response.send_message("通知チャンネル設定完了")
