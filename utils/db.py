import asyncpg

async def init_db_pool(DATABASE_URL: str):
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:

        # guild_settings
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            notify_channel TEXT
        );
        """)

        # slots（既にあってもOK）
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS slots (
            id BIGSERIAL PRIMARY KEY,
            guild_id BIGINT,
            start_at TIMESTAMPTZ
        );
        """)

        # ✅ ここが超重要
        await conn.execute("""
        ALTER TABLE slots ADD COLUMN IF NOT EXISTS user_id TEXT;
        """)

        await conn.execute("""
        ALTER TABLE slots ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT false;
        """)

    print("✅ DB tables ensured")
    return pool