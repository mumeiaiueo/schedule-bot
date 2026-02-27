# main.py
import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot_forever

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN が未設定です")
    await run_bot_forever(TOKEN)

asyncio.run(main())