import asyncpg

async def init_db_pool(dsn: str):
    return await asyncpg.create_pool(
        dsn=dsn,
        ssl="require",
        statement_cache_size=0,
        min_size=1,
        max_size=5,
        command_timeout=30,
    )