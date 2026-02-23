import os
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

class TestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="テストボタン", style=discord.ButtonStyle.success, custom_id="test_btn")
    async def test_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        # これが無いと「インタラクションに失敗しました」になりやすい
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("✅ ボタン押せた！(最小ボット動作OK)", ephemeral=True)

@tree.command(name="ping", description="疎通確認")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong ✅", ephemeral=True)

@tree.command(name="panel", description="テスト用パネルを出す")
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message("👇テストパネル", view=TestView())

@client.event
async def on_ready():
    # コマンド反映
    await tree.sync()
    # 永続View登録（再起動後もボタン生きる）
    client.add_view(TestView())
    print(f"✅ Logged in as {client.user}")

client.run(TOKEN)