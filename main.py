# main.py
import os
import asyncio
from dotenv import load_dotenv

from bot_app import run_bot

load_dotenv()

def _must_env(name: str) -> str:
    v = os.getenv(name)
    if not v or not v.strip():
        raise RuntimeError(f"{name} が未設定です（RenderのEnvironmentに追加してね）")
    return v.strip()

async def main():
    token = _must_env("DISCORD_TOKEN")
    await run_bot(token)

if __name__ == "__main__":
    asyncio.run(main())