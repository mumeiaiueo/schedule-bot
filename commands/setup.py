import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup", description="募集パネル作成ウィザードを開く")
    async def setup_cmd(interaction: discord.Interaction):
        try:
            # ephemではなく「ウィザードメッセージをチャンネルに出す」
            # →ボタン押して操作する設計
            embed = build_setup_embed({
                "step": 1, "day": "today", "start": None, "end": None,
                "interval": None, "notify_channel_id": None,
                "everyone": False, "title": None
            })
            view = build_setup_view({"step": 1, "day": "today"})
            await interaction.response.send_message(embed=embed, view=view)

        except Exception:
            print("setup error")
            print(traceback.format_exc())
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ /setup 内部エラー（ログ確認）", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ /setup 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass