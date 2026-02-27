# main.py
print("🔥 BOOT MARKER 3-split STABLE 🔥")

import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN or not TOKEN.strip():
    raise RuntimeError("DISCORD_TOKEN が未設定です")

asyncio.run(run_bot(TOKEN))