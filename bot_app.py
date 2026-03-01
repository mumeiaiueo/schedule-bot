# bot_app.py
import traceback
import discord
from discord.ext import tasks
from discord import app_commands

from utils.data_manager import DataManager
from bot_interact import handle_interaction


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()
        self.setup_state = {}

    async def setup_hook(self):
        # ここでコマンド登録（commandsフォルダ消したなら、ここに直書きが一番安全）
        self._register_commands()

        await self.tree.sync()
        self.reminder_loop.start()

    def _register_commands(self):
        # /setup（募集パネル作成ウィザード開始）
        @self.tree.command(name="setup", description="募集パネル作成ウィザード")
        async def setup_cmd(interaction: discord.Interaction):
            try:
                # ✅ スラッシュコマンドのdeferは「コマンド内」でのみ行う
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)

                # 初期表示は bot_interact の wizard に任せる（custom_id無しでもOKにしてるならそれで）
                # もし「開始用の表示」が必要なら、ここで embed/view を送ってOK
                from views.setup_wizard import build_setup_embed, build_setup_view
                from bot_interact import _ensure_setup_state  # 使えるなら

                st = _ensure_setup_state(self, interaction.user.id)
                embed = build_setup_embed(st)
                view = build_setup_view(st)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)

            except Exception:
                print("setup_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ setup 内部エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

        # /reset（今日/明日削除）※DataManager側に関数が必要
        @self.tree.command(name="reset", description="今日/明日の募集を削除")
        async def reset_cmd(interaction: discord.Interaction):
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)

                # ここは「今日/明日選ぶUI」を作るか、引数で受けるかは後でOK
                await interaction.followup.send("✅ /reset は後で実装（仕様どおりに作る）", ephemeral=True)
            except Exception:
                print("reset_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ reset 内部エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

        # /manager_role（管理ロール設定）※DataManager側に set_manager_role_id が必要
        @self.tree.command(name="manager_role", description="管理ロールを設定/解除")
        @app_commands.describe(role="管理に使うロール（解除したい場合は未指定）")
        async def manager_role_cmd(interaction: discord.Interaction, role: discord.Role | None = None):
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer(ephemeral=True)

                if isinstance(interaction.user, discord.Member) and not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ サーバー管理者のみ実行できます", ephemeral=True)
                    return

                ok, msg = await self.dm.set_manager_role_id(
                    guild_id=str(interaction.guild_id),
                    role_id=(role.id if role else None),
                )
                await interaction.followup.send(("✅ " if ok else "❌ ") + msg, ephemeral=True)

            except Exception:
                print("manager_role_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ manager_role 内部エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 安定運用ルール
        - component / modal だけここで defer → bot_interactへ
        - application_command は tree に渡す（ここで defer しない）
        """
        try:
            if interaction.type == discord.InteractionType.component:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()  # ✅ componentのみ
                except Exception:
                    pass
                await handle_interaction(self, interaction)
                return

            if interaction.type == discord.InteractionType.modal_submit:
                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer(ephemeral=True)
                except Exception:
                    pass
                await handle_interaction(self, interaction)
                return

            # ✅ スラッシュコマンドはdiscord.py標準の tree 側へ
            await self.tree._from_interaction(interaction)

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            await self.dm.send_3min_reminders(self)
        except Exception:
            print("❌ reminder loop error")
            print(traceback.format_exc())


async def run_bot(token: str):
    bot = BotApp()
    async with bot:
        await bot.start(token)