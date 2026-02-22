import discord
from discord import app_commands
from utils.time_utils import generate_slots
from utils.data_manager import load_data, save_data, get_guild
from views.slot_view import SlotView, build_panel_text

def setup(bot: discord.Client):

    @bot.tree.command(name="create", description="開始/終了と間隔から予約パネルを作成")
    @app_commands.describe(start="開始 例 18:00", end="終了 例 01:00")
    @app_commands.choices(interval=[
        app_commands.Choice(name="20", value=20),
        app_commands.Choice(name="25", value=25),
        app_commands.Choice(name="30", value=30),
    ])
    async def create(
        interaction: discord.Interaction,
        start: str,
        end: str,
        interval: app_commands.Choice[int],
    ):
        # ⭐ これを最速で返す（3秒制限対策）
        await interaction.response.defer(thinking=True)

        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）", ephemeral=True)
                return

            data = load_data()
            g = get_guild(data, interaction.guild.id)

            # 状態リセットして新規作成
            g["slots"] = slots
            g["reservations"] = {}
            g["reminded"] = []
            save_data(data)

            # ⭐ 日付またぎ判定用のメタ情報を保存
start_h, start_m = map(int, start.split(":"))
end_h, end_m = map(int, end.split(":"))
start_min = start_h * 60 + start_m
end_min = end_h * 60 + end_m
cross_midnight = end_min <= start_min

g["meta"] = {
    "start_min": start_min,
    "cross_midnight": cross_midnight
}
            # パネル送信
            view = SlotView(guild_id=interaction.guild.id, page=0)
            msg = await interaction.followup.send(content=build_panel_text(g), view=view)

            # パネルID保存
            data = load_data()
            g = get_guild(data, interaction.guild.id)
            g["panel"]["channel_id"] = msg.channel.id
            g["panel"]["message_id"] = msg.id
            save_data(data)

        except Exception as e:
            # ⭐ 失敗時も必ず返信（Unknown interaction防止）
            await interaction.followup.send(f"❌ create失敗: {type(e).__name__}: {e}", ephemeral=True)
