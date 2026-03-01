import traceback
import discord
from discord import app_commands
from utils.time_utils import jst_today_date


class ResetView(discord.ui.View):
    def __init__(self, guild_id: str, channel_id: str, dm):
        super().__init__(timeout=60)
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.dm = dm

    @discord.ui.button(label="今日", style=discord.ButtonStyle.danger, custom_id="reset:today")
    async def today_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._do(interaction, offset=0)

    @discord.ui.button(label="明日", style=discord.ButtonStyle.danger, custom_id="reset:tomorrow")
    async def tomorrow_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._do(interaction, offset=1)

    async def _do(self, interaction: discord.Interaction, offset: int):
        if not await self.dm.is_manager(interaction):
            await interaction.response.send_message("❌ 管理者/管理ロールのみ実行できます", ephemeral=True)
            return
        day = str(jst_today_date(offset))
        n = await self.dm.delete_panels_by_day(self.guild_id, self.channel_id, day)
        await interaction.response.send_message(f"✅ {day} の募集を削除しました（{n}件）", ephemeral=True)
        try:
            self.stop()
        except Exception:
            pass


def register(tree: app_commands.CommandTree, dm):
    @tree.command(name="reset", description="今日 or 明日の募集を削除（管理者/管理ロールのみ）")
    async def reset_cmd(interaction: discord.Interaction):
        try:
            if not await dm.is_manager(interaction):
                await interaction.response.send_message("❌ 管理者/管理ロールのみ実行できます", ephemeral=True)
                return

            view = ResetView(str(interaction.guild_id), str(interaction.channel_id), dm)
            await interaction.response.send_message("削除する日を選んでください（即削除・確認なし）", view=view, ephemeral=True)

        except Exception:
            print("reset error")
            print(traceback.format_exc())
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ /reset 内部エラー（ログ確認）", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ /reset 内部エラー（ログ確認）", ephemeral=True)
            except Exception:
                pass