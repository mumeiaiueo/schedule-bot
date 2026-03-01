# commands/setup_channel.py
import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def _new_state() -> dict:
    return {
        "step": 1,
        "day": "today",
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
    @tree.command(name="setup_channel", description="このチャンネルに募集パネルを作成（ウィザード）")
    async def setup_channel(interaction: discord.Interaction):
        try:
            client = interaction.client
            if not hasattr(client, "setup_state"):
                client.setup_state = {}

            st = _new_state()
            client.setup_state[interaction.user.id] = st

            embed = build_setup_embed(st)
            view = build_setup_view(st)

            # 🔥 deferは使わない
            await interaction.response.send_message(
                "📅 設定を進めてください（デフォルト：今日）",
                embed=embed,
                view=view,
                ephemeral=True,
            )

        except Exception:
            print("❌ setup_channel error")
            print(traceback.format_exc())
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ setup_channel 内部エラー", ephemeral=True)
            except Exception:
                pass