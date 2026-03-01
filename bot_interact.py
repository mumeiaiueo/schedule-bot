import traceback
import discord
from datetime import datetime

from views.setup_wizard import build_setup_embed, build_setup_view, TitleModal


def _default_state():
    return {
        "step": 1,
        "day": "today",
        "start": None,
        "end": None,
        "interval": None,
        "title": None,
        "everyone": False,
    }


def _get_state(bot, user_id):
    if user_id not in bot.setup_state:
        bot.setup_state[user_id] = _default_state()
    return bot.setup_state[user_id]


async def handle_interaction(bot: discord.Client, interaction: discord.Interaction):
    try:
        data = interaction.data or {}
        custom_id = data.get("custom_id")
        values = data.get("values")

        if not custom_id:
            return

        # ------------------------
        # SETUP WIZARD
        # ------------------------

        if custom_id.startswith("setup:"):

            state = _get_state(bot, interaction.user.id)

            # 日付切替
            if custom_id == "setup:today":
                state["day"] = "today"

            elif custom_id == "setup:tomorrow":
                state["day"] = "tomorrow"

            # 時刻選択
            elif custom_id == "setup:start":
                state["start"] = values[0]

            elif custom_id == "setup:end":
                state["end"] = values[0]

            elif custom_id == "setup:interval":
                state["interval"] = int(values[0])

            # タイトル入力
            elif custom_id == "setup:title":
                await interaction.response.send_modal(TitleModal())
                return

            # 次へ
            elif custom_id == "setup:next":
                state["step"] = 2

            # 作成
            elif custom_id == "setup:create":

                if not state["start"] or not state["end"] or not state["interval"]:
                    await interaction.followup.send("⚠️ 未入力項目があります", ephemeral=True)
                    return

                await interaction.followup.send("✅ 作成処理（次でDB接続）", ephemeral=True)
                return

            # 再描画
            embed = build_setup_embed(state)
            view = build_setup_view(state)
            await interaction.message.edit(embed=embed, view=view)

    except Exception:
        print(traceback.format_exc())