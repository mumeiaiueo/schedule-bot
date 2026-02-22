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
        interval: app_commands.Choice[int]
    ):
        await interaction.response.defer()

        # 枠生成（HH:MMのみ）
        try:
            slots = generate_slots(start, end, interval.value)
            if not slots:
                await interaction.followup.send("❌ 枠が作れません（時間か間隔を確認）")
                return
        except:
            await interaction.followup.send("❌ 時間は HH:MM（例 18:00）で入力してね")
            return

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        # 状態リセットして新規作成
        g["slots"] = slots
        g["reservations"] = {}
        g["reminded"] = []
        save_data(data)

        # パネル送信
        view = SlotView(guild_id=interaction.guild.id)
        msg = await interaction.followup.send(content=build_panel_text(g), view=view)

        # パネルID保存（更新に使う）
        data = load_data()
        g = get_guild(data, interaction.guild.id)
        g["panel"]["channel_id"] = msg.channel.id
        g["panel"]["message_id"] = msg.id
        save_data(data)
