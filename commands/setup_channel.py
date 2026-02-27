# commands/setup_channel.py
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネルに募集パネル作成ウィザードを表示（管理者）")
    async def setup_channel(interaction: discord.Interaction):
        # 管理者のみ
        if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ 管理者のみ実行できます", ephemeral=True)
            return

        # ✅ ウィザード初期状態は main.py 側で持つ（client.setup_state）
        # ただし /setup_channel からも動くよう「最低限」初期状態をmessage側に出す
        st = {
            "page": 1,
            "day": None,
            "start_hour": None,
            "start_min": None,
            "end_hour": None,
            "end_min": None,
            "start": None,
            "end": None,
            "interval": None,
            "notify_channel_id": None,
            "everyone": False,
            "title": None,
        }

        embed = build_setup_embed(st)
        view = build_setup_view(st)

        await interaction.response.send_message("✅ ウィザードを表示しました", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)