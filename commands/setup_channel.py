# commands/setup_channel.py
import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネル用の予約枠を作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        try:
            # ✅ 最重要：3秒以内にまずACK（これが無いと「応答しない」）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            # 初期状態（ユーザーごとに状態管理したいなら client.setup_state を使う想定）
            st = {
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

            await interaction.followup.send(
                "📅 今日 or 明日を選んでください",
                embed=embed,
                view=view,
                ephemeral=True,
            )

        except Exception:
            print("❌ setup_channel error")
            print(traceback.format_exc())
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ setup_channel 内部エラー（ログ確認）", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ setup_channel 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass