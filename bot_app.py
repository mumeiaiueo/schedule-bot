# bot_app.py
import os
import traceback
import discord
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_interaction
from commands.setup import register as register_setup


TOKEN = os.getenv("DISCORD_TOKEN")


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()
        self.setup_state = {}

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        await self.tree.sync()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        try:
            # componentはここでACK（40060対策）
            if interaction.type == discord.InteractionType.component:
                if not interaction.response.is_done():
                    await interaction.response.defer()
                await handle_interaction(self, interaction)
                return

            # modal_submit は bot_interact 側（Modal.on_submit）で処理するので何もしない
            # slash commandは標準処理
            await super().on_interaction(interaction)

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())


if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")
    BotApp().run(TOKEN)