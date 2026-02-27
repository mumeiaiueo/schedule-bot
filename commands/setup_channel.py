# commands/setup_channel.py
import discord

from views.setup_wizard import build_setup_embed, build_setup_view


def register(tree: discord.app_commands.CommandTree, dm):
    @tree.command(
        name="setup_channel",
        description="このチャンネルに予約パネルを作成（ウィザード）"
    )
    async def setup_channel(interaction: discord.Interaction):
        # ここは「あなたにだけ見える」ウィザード表示（スクショの挙動）
        # ※ephemeral=False にすると全員に見える
        try:
            client = interaction.client

            # main.py の MyClient にある状態保存を使う（無ければ最低限の初期状態）
            if hasattr(client, "_get_setup_state"):
                st = client._get_setup_state(interaction.user.id)
            else:
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

            await interaction.response.send_message(
                "今日 or 明日 を選んでください👇",
                embed=embed,
                view=view,
                ephemeral=True,  # ←スクショ通り「あなたにだけ表示」
            )

        except Exception as e:
            # ここで落ちると「コマンドはあるのに反応しない」になりがちなので握って返す
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"❌ setup_channel エラー: {repr(e)}", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ setup_channel エラー: {repr(e)}", ephemeral=True)
            except Exception:
                pass