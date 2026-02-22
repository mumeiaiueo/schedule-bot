import discord
from discord import app_commands
from utils.data_manager import load_data, save_data, get_guild
from utils.time_utils import build_slots
from views.slot_view import SlotView

def setup(bot: discord.Client):

    @bot.tree.command(name="create", description="予約枠パネルを作成")
    @app_commands.describe(start="開始 (例 12:00)", end="終了 (例 18:00)")
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
        await interaction.response.defer(ephemeral=True)

        try:
            slots = build_slots(start, end, interval.value)
        except Exception:
            await interaction.followup.send("❌ 時刻は HH:MM、間隔は20/25/30のみ", ephemeral=True)
            return

        data = load_data()
        g = get_guild(data, interaction.guild.id)

        # データ更新（新規作成なので初期化）
        g["slots"] = slots
        g["reservations"] = {}
        g["reminded"] = []

        # パネル本文（最初は緑だけ）
        panel_text = "📅 予約枠\n" + "\n".join([f"🟢 {s['start_iso'][11:16]}" for s in slots])

        # このチャンネルにパネルを出す
        msg = await interaction.channel.send(panel_text, view=SlotView(interaction.guild.id))

        g["panel_channel_id"] = interaction.channel.id
        g["panel_message_id"] = msg.id

        save_data(data)

        # 再起動してもボタン生きるように登録
        bot.add_view(SlotView(interaction.guild.id))

        await interaction.followup.send("✅ 予約パネルを作成しました", ephemeral=True)
