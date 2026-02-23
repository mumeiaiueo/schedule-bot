import asyncpg

async def init_db_pool(dsn: str):
    # Supabase / pooler 対策：
    # - SSL必須
    # - prepared statementキャッシュを無効化（pgbouncer系で事故りやすい）
    pool = await asyncpg.create_pool(
        dsn=dsn,
        ssl="require",
        statement_cache_size=0,
        max_size=5,
        min_size=1,
        command_timeout=30,
    )

    # ここでテーブル作成などをしているなら、その処理も残してOK
    # （あなたの既存db.pyに "ensure tables" がある場合は下に続けて書いてOK）
    return pool