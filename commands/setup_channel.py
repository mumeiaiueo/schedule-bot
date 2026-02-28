# commands/setup_channel.py
import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def _default_state():
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
            # ✅ 状態を bot に保存（ユーザーごと）
            bot = interaction.client
            if not hasattr(bot, "setup_state") or bot.setup_state is None:
                bot.setup_state = {}

            st = bot.setup_state.get(interaction.user.id)
            if st is None:
                st = _default_state()
                bot.setup_state[interaction.user.id] = st

            embed = build_setup_embed(st)
            view = build_setup_view(st)

            # ✅ defer+followup じゃなくて、最初から send_message でACK確定（応答なし対策）
            await interaction.response.send_message(
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