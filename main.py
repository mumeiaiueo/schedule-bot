import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager
from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)

    async def on_ready(self):
        await self.tree.sync()
        print(f"✅ Logged in as {self.user}")
        if not reminder_loop.is_running():
            reminder_loop.start(self)

    async def on_interaction(self, interaction: discord.Interaction):
        # ボタン/セレクトの処理
        if interaction.type != discord.InteractionType.component:
            return

        cid = interaction.data.get("custom_id") if interaction.data else None
        if not cid or not cid.startswith("panel:"):
            return

        # 3秒失敗対策
        await interaction.response.defer(ephemeral=True)

        # slotボタン（予約/キャンセル トグル）
        if cid.startswith("panel:slot:"):
            _, _, pid, sid = cid.split(":")
            panel_id = int(pid)
            slot_id = int(sid)

            ok, msg = await self.dm.toggle_reserve(
                slot_id=slot_id,
                user_id=str(interaction.user.id),
                user_name=interaction.user.display_name,
            )
            await interaction.followup.send(msg, ephemeral=True)
            await self.dm.render_panel(self, panel_id)
            return

        # 休憩切替（管理者のみ）→ セレクトを出す
        if cid.startswith("panel:breaktoggle:"):
            _, _, pid = cid.split(":")
            panel_id = int(pid)

            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                return

            view = await self.dm.build_break_select_view(panel_id)
            await interaction.followup.send("休憩にする/解除する時間を選んで👇", view=view, ephemeral=True)
            return

        # 休憩セレクト（管理者のみ）
        if cid.startswith("panel:breakselect:"):
            _, _, pid = cid.split(":")
            panel_id = int(pid)

            if not interaction.user.guild_permissions.administrator:
                await interaction.followup.send("❌ 管理者のみ実行できます", ephemeral=True)
                return

            values = interaction.data.get("values") or []
            if not values:
                await interaction.followup.send("❌ 選択を取得できませんでした", ephemeral=True)
                return

            slot_id = int(values[0])
            ok, msg = await self.dm.toggle_break_slot(panel_id, slot_id)
            await interaction.followup.send(("✅ " if ok else "❌ ") + msg, ephemeral=True)
            await self.dm.render_panel(self, panel_id)
            return


client = MyClient()

@tasks.loop(seconds=20)
async def reminder_loop(bot: MyClient):
    await bot.dm.send_3min_reminders(bot)

client.run(TOKEN)