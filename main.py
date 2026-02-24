print("🔥 BOOT MARKER v2026-02-24-stable-reminder 🔥")

import asyncio
import os
import discord
from discord.ext import tasks
from dotenv import load_dotenv

import socket
import traceback
from urllib.parse import urlparse

from utils.data_manager import DataManager
from commands.setup_channel import register as register_setup
from commands.reset_channel import register as register_reset
from commands.remind_channel import register as register_remind
from commands.notify import register as register_notify

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

# Supabaseは DataManager/utils/db.py 側で使うけど、
# DNSチェックに使うのでここでも読む
SUPABASE_URL = os.getenv("SUPABASE_URL")

intents = discord.Intents.default()


def supabase_host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except Exception:
        return None


class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = discord.app_commands.CommandTree(self)
        self.dm = DataManager()
        self._synced = False

        # reminder のバックオフ制御
        self._reminder_fail_count = 0
        self._reminder_pause_until = 0.0  # loop.time() 기준

    async def setup_hook(self):
        register_setup(self.tree, self.dm)
        register_reset(self.tree, self.dm)
        register_remind(self.tree, self.dm)
        register_notify(self.tree, self.dm)

    async def on_ready(self):
        # sync は起動後1回だけ（429対策）
        if not self._synced:
            try:
                await self.tree.sync()
                self._synced = True
                print("✅ commands synced")
            except Exception as e:
                print("⚠️ tree.sync failed:", repr(e))
                print(traceback.format_exc())

        print(f"✅ Logged in as {self.user}")

        if not reminder_loop.is_running():
            reminder_loop.start(self)


client = MyClient()


@tasks.loop(seconds=60, reconnect=True)
async def reminder_loop(bot: MyClient):
    # 再接続直後など
    if not bot.is_ready():
        return

    loop = asyncio.get_running_loop()

    # バックオフ中なら何もしない
    if bot._reminder_pause_until and loop.time() < bot._reminder_pause_until:
        return

    try:
        await bot.dm.send_3min_reminders(bot)

        # 成功したら失敗回数リセット
        bot._reminder_fail_count = 0
        bot._reminder_pause_until = 0.0

    except Exception as e:
        bot._reminder_fail_count += 1

        print("reminder_loop error:", repr(e))
        print(traceback.format_exc())

        # 失敗が続くと待ち時間を伸ばす（最大10分）
        # 1回目:60s, 2回目:120s, 3回目:240s, ... 最大600s
        backoff = min(600, 60 * (2 ** (bot._reminder_fail_count - 1)))

        # DNS/ネット系っぽいときは最初から少し長めでもOK
        msg = repr(e)
        if "Name or service not known" in msg or "ConnectError" in msg or "Temporary failure in name resolution" in msg:
            backoff = max(backoff, 120)

        bot._reminder_pause_until = loop.time() + backoff
        print(f"⏸ reminder paused for {backoff}s (fail_count={bot._reminder_fail_count})")


@reminder_loop.before_loop
async def before_reminder_loop():
    await client.wait_until_ready()
    await asyncio.sleep(10)  # 起動直後の不安定回避

    host = supabase_host_from_url(SUPABASE_URL)
    if not host:
        print("⚠️ SUPABASE_URL is missing or invalid. DNS check skipped.")
        return

    # DNS解決テスト（失敗しても落とさない）
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ DNS check OK: {host} -> {ip}")
    except Exception as e:
        print("⚠️ DNS check failed:", repr(e))


async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN が未設定です")

    # 永久ループで落ちても復帰
    while True:
        try:
            async with client:
                await client.start(TOKEN)

        except discord.HTTPException as e:
            # 429など
            print("discord HTTPException:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(90)

        except Exception as e:
            print("fatal error:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(90)


asyncio.run(main())