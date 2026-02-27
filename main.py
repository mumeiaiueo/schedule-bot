# main.py
print("🔥 BOOT MARKER split v2026-02-27 STABLE 🔥")

import os
import asyncio
from dotenv import load_dotenv

from bot_core import run_bot

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN or not TOKEN.strip():
    raise RuntimeError("DISCORD_TOKEN が未設定です（Render の Environment を確認）")

asyncio.run(run_bot(TOKEN))