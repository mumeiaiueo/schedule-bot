import asyncio
import os
import traceback

import discord

from bot_app import run_bot

TOKEN = os.getenv("DISCORD_TOKEN")

async def run_forever():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN 未設定")

    backoff = 5
    while True:
        try:
            await run_bot(TOKEN.strip())
            backoff = 5  # 正常終了したら戻す
        except discord.HTTPException as e:
            # 429 対策：落ちずに待って再試行
            status = getattr(e, "status", None)
            if status == 429:
                wait = 90  # 取得できない時の保険
                # discord.py が "retry after XXs" を出してるので基本はこれでOK
                print(f"⚠️ Discord 429 rate limit. sleep {wait}s then retry")
                await asyncio.sleep(wait)
                continue

            print("❌ discord.HTTPException:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)
        except Exception as e:
            print("❌ fatal error:", repr(e))
            print(traceback.format_exc())
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)

if __name__ == "__main__":
    asyncio.run(run_forever())