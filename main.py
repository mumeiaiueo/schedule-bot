# main.py
print("🔥 BOOT main.py v2026-02-28 STABLE (retry/backoff) 🔥")

import asyncio
import os
import random
import traceback
from dotenv import load_dotenv

from bot_app import run_bot_once


load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN", "").strip()

# Discordログイン失敗→即再起動の無限ループを止めるためのバックオフ
MIN_WAIT = 10
MAX_WAIT = 15 * 60  # 15分


def _calc_backoff(attempt: int) -> int:
    # 10, 20, 40, 80 ... 最大15分 + ジッタ
    base = min(MAX_WAIT, MIN_WAIT * (2 ** max(0, attempt - 1)))
    jitter = random.randint(0, 10)
    return int(base + jitter)


async def main():
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN が未設定です（RenderのEnvironmentで設定して）")

    attempt = 0
    while True:
        try:
            attempt += 1
            print(f"🚀 run_bot_once start (attempt={attempt})")
            await run_bot_once(TOKEN)
            # 通常ここには戻らない（bot停止時だけ）
            print("🛑 bot stopped normally. sleep 30s then restart.")
            await asyncio.sleep(30)

        except Exception as e:
            msg = repr(e)
            print("💥 bot crashed:", msg)
            print(traceback.format_exc())

            # 429 / Cloudflare / 一時的なネットワークは長めに待つ
            wait_s = _calc_backoff(attempt)

            # よく出るやつはさらに最低2分待つ（BANループ防止）
            hot_words = [
                "429",
                "Too Many Requests",
                "Cloudflare",
                "Access denied",
                "rate limited",
            ]
            if any(w in msg for w in hot_words):
                wait_s = max(wait_s, 120)

            print(f"⏸ restart backoff: {wait_s}s")
            await asyncio.sleep(wait_s)


if __name__ == "__main__":
    asyncio.run(main())