# commands/setup.py
import traceback
import discord
from discord import app_commands

from views.setup_wizard import build_setup_embed, build_setup_view


def _new_state() -> dict:
    return {
        "step": 1,
        "day": "today",  # デフォルト今日
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
        "wizard_message_id": None,
        "wizard_channel_id": None,
    }


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="setup", description="募集パネルを作成（ウィザード）")
    async def setup(interaction: discord.Interaction):
        try:
            # まずACK（エラー防止）
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)

            client = interaction.client
            if not hasattr(client, "setup_state"):
                client.setup_state = {}

            st = _new_state()
            client.setup_state[interaction.user.id] = st

            # ✅ ウィザード本体は「チャンネルに投稿」(非ephemeral)
            # （タイトル入力Modal後も安全に編集できるようにするため）
            embed = build_setup_embed(st)
            view = build_setup_view(st)

            msg = await interaction.channel.send("🧩 枠作成ウィザード", embed=embed, view=view)

            st["wizard_message_id"] = msg.id
            st["wizard_channel_id"] = interaction.channel_id

            await interaction.followup.send("✅ ウィザードを表示しました。上のメッセージから操作してね。", ephemeral=True)

        except Exception:
            print("❌ /setup error")
            print(traceback.format_exc())
            try:
                await interaction.followup.send("❌ /setup 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass