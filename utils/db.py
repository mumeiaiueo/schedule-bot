import asyncpg

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id BIGINT PRIMARY KEY,
  notify_channel BIGINT,
  panel_channel_id BIGINT,
  panel_message_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS slots (
  id BIGSERIAL PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  slot_time TEXT NOT NULL,         -- "HH:MM"
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (guild_id, slot_time)
);

CREATE TABLE IF NOT EXISTS reservations (
  id BIGSERIAL PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  slot_time TEXT NOT NULL,         -- "HH:MM"
  user_id BIGINT,
  reminded BOOLEAN DEFAULT FALSE,
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (guild_id, slot_time)
);
"""

async def init_db_pool(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute(CREATE_SQL)
    return pool
