import os
import asyncio
import traceback

import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

from utils.data_manager import DataManager
from bot_interact import handle_interaction
from utils.time_utils import jst_today_date

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")


class BotApp(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.dm = DataManager()
        self.setup_state: dict[int, dict] = {}
        self._synced = False

    async def setup_hook(self):
        # =========================
        # /setup  募集パネル作成（ウィザード）
        # =========================
        @self.tree.command(name="setup", description="このチャンネルに募集パネルを作成（ウィザード）")
        async def setup_cmd(interaction: discord.Interaction):
            from views.setup_wizard import build_setup_embed, build_setup_view
            from bot_interact import _default_setup_state

            try:
                await interaction.response.defer(ephemeral=True)

                st = _default_setup_state()
                # デフォルト：今日
                st["day"] = "today"
                self.setup_state[interaction.user.id] = st

                embed = build_setup_embed(st)
                view = build_setup_view(st)
                await interaction.followup.send("設定を進めてね（デフォルト：今日）", embed=embed, view=view, ephemeral=True)
            except Exception:
                print("setup_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ /setup エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

        # =========================
        # /reset 今日/明日の募集削除
        # =========================
        @self.tree.command(name="reset", description="このチャンネルの募集を削除（今日/明日）")
        @app_commands.describe(day="today=今日 / tomorrow=明日")
        async def reset_cmd(interaction: discord.Interaction, day: str = "today"):
            try:
                await interaction.response.defer(ephemeral=True)

                # 管理者/管理ロールのみ
                if not await self.dm.is_manager(interaction):
                    await interaction.followup.send("❌ 管理者/管理ロールのみ実行できます", ephemeral=True)
                    return

                if day not in ("today", "tomorrow"):
                    await interaction.followup.send("❌ day は today / tomorrow のみ", ephemeral=True)
                    return

                day_date = jst_today_date(0 if day == "today" else 1)
                ok = await self.dm.delete_panel_by_channel_day(
                    guild_id=str(interaction.guild_id),
                    channel_id=str(interaction.channel_id),
                    day_date=day_date,
                )
                if ok:
                    await interaction.followup.send(f"✅ {day_date} の募集を削除しました", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ {day_date} の募集は見つかりませんでした", ephemeral=True)
            except Exception:
                print("reset_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ /reset エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

        # =========================
        # /manager_role 管理ロール設定（サーバー管理者のみ）
        # =========================
        @self.tree.command(name="manager_role", description="管理ロールを設定（このロール持ちは管理操作OK）")
        @app_commands.describe(role="管理に使うロール（解除したい場合は未指定で実行）")
        async def manager_role_cmd(interaction: discord.Interaction, role: discord.Role | None = None):
            try:
                await interaction.response.defer(ephemeral=True)

                # サーバー管理者のみが設定できる
                if isinstance(interaction.user, discord.Member) and not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ サーバー管理者のみ実行できます", ephemeral=True)
                    return

                ok, msg = await self.dm.set_manager_role_id(
                    guild_id=str(interaction.guild_id),
                    role_id=(role.id if role else None),
                )
                await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                print("manager_role_cmd error")
                print(traceback.format_exc())
                try:
                    await interaction.followup.send("❌ /manager_role エラー（ログ確認）", ephemeral=True)
                except Exception:
                    pass

        # コマンド同期（必要な時だけ）
        if os.getenv("SYNC_COMMANDS", "0") == "1" and not self._synced:
            await self.tree.sync()
            self._synced = True
            print("✅ commands synced")

        # 3分前通知ループ
        if not self.reminder_loop.is_running():
            self.reminder_loop.start()

    async def on_ready(self):
        print(f"✅ Logged in as {self.user}")

    async def on_interaction(self, interaction: discord.Interaction):
        """
        ✅ 40060対策：
        - setup:title:open（モーダルを開く）だけは defer しない
        - それ以外の component は defer してから bot_interact に渡す
        - modal_submit は defer(ephemeral=True) してから渡す
        """
        try:
            if interaction.type == discord.InteractionType.component:
                cid = (interaction.data or {}).get("custom_id") or ""
                # モーダルを開くボタンは defer すると send_modal できない
                if cid == "setup:title:open":
                    await handle_interaction(self, interaction)
                    return

                try:
                    if not interaction.response.is_done():
                        await interaction.response.defer()
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

            # slash command は通常処理
            await self.tree._from_interaction(interaction)

        except Exception:
            print("❌ on_interaction error")
            print(traceback.format_exc())

    @tasks.loop(seconds=30)
    async def reminder_loop(self):
        try:
            await self.dm.send_3min_reminders(self)
        except Exception:
            print("❌ reminder_loop error")
            print(traceback.format_exc())


async def run_bot(token: str):
    bot = BotApp()

    # 429の再発防止：簡易バックオフ
    backoff = 5
    while True:
        try:
            await bot.start(token)
            return
        except discord.HTTPException as e:
            if getattr(e, "status", None) == 429:
                print(f"⚠️ 429 Too Many Requests. sleep {backoff}s then retry...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
                continue
            raise
        except Exception:
            print("❌ fatal error (run_bot)")
            print(traceback.format_exc())
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 300)