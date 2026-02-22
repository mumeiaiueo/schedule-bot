import asyncpg

async def init_db_pool(DATABASE_URL: str):
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        # 既にテーブルがある前提でも安全に実行できる（存在しなければ作る）
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_settings (
              guild_id TEXT PRIMARY KEY,
              notify_channel TEXT
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS slots (
              id BIGSERIAL PRIMARY KEY,
              guild_id BIGINT,
              start_at TIMESTAMPTZ
            );
            """
        )

        # ✅ ここが重要：列が無ければ追加（何回起動してもOK）
        await conn.execute("ALTER TABLE slots ADD COLUMN IF NOT EXISTS user_id TEXT;")
        await conn.execute("ALTER TABLE slots ADD COLUMN IF NOT EXISTS notified BOOLEAN DEFAULT false;")

    return pool