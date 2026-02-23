import asyncpg
import ssl

async def init_db_pool(dsn: str):
    """
    Supabase(pooler/pgbouncer)向け安定設定
    - SSLを明示的に強制
    - statement cache を無効化（pgbouncerでの事故防止）
    - タイムアウト短め
    """
    ssl_ctx = ssl.create_default_context()

    pool = await asyncpg.create_pool(
        dsn=dsn,
        ssl=ssl_ctx,              # ✅ ここが重要：SSL強制
        statement_cache_size=0,   # ✅ pgbouncer対策
        max_size=5,
        min_size=1,
        command_timeout=30,
    )
    return pool