# commands/setup_channel.py
import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def _new_state() -> dict:
    return {
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


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup_channel", description="このチャンネル用の予約枠を作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        try:
            # 3秒以内ACK（これが無いと「アプリケーションが応答しません」）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            client = interaction.client
            if not hasattr(client, "setup_state"):
                client.setup_state = {}

            st = _new_state()
            st["day"] = "today"   
            client.setup_state[interaction.user.id] = st

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