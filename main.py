# main.py
import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")
    await run_bot(TOKEN.strip())

asyncio.run(main())