# main.py
print("🔥 BOOT main.py v2026-02-27 split-entry 🔥")

import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN が未設定です（RenderのEnvironmentに入れて）")
    await run_bot(TOKEN.strip())

asyncio.run(main())