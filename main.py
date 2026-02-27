# main.py
import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    if not TOKEN or not TOKEN.strip():
        raise RuntimeError("DISCORD_TOKEN が未設定です")
    await run_bot(TOKEN)

asyncio.run(main())