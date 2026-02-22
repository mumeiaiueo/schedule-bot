import asyncpg

MIGRATE_SQL = """
-- ① guild_settings が古いスキーマの場合に直す
DO $$
BEGIN
  -- テーブルが無ければ何もしない（後でCREATEで作る）
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='guild_settings'
  ) THEN
    RETURN;
  END IF;

  -- server_id という古い列があって guild_id が無いなら rename
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='server_id'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='guild_id'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings RENAME COLUMN server_id TO guild_id';
  END IF;

  -- guild_id が無い場合は追加
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='guild_id'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD COLUMN guild_id BIGINT';
  END IF;

  -- notify_channel が無い場合は追加
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='notify_channel'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD COLUMN notify_channel BIGINT';
  END IF;

  -- panel_channel_id が無い場合は追加
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='panel_channel_id'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD COLUMN panel_channel_id BIGINT';
  END IF;

  -- panel_message_id が無い場合は追加
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='panel_message_id'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD COLUMN panel_message_id BIGINT';
  END IF;

  -- created_at が無い場合は追加
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='guild_settings' AND column_name='created_at'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD COLUMN created_at TIMESTAMPTZ DEFAULT NOW()';
  END IF;

  -- PKが無ければ作る（guild_idがNULLの行があると失敗するので削除）
  EXECUTE 'DELETE FROM guild_settings WHERE guild_id IS NULL';
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.guild_settings'::regclass AND contype='p'
  ) THEN
    EXECUTE 'ALTER TABLE guild_settings ADD PRIMARY KEY (guild_id)';
  END IF;

EXCEPTION WHEN undefined_table THEN
  -- 何もしない（後でCREATE）
  NULL;
END $$;
"""

CREATE_SQL = """
-- guild_settings（無ければ作る）
CREATE TABLE IF NOT EXISTS guild_settings (
  guild_id BIGINT PRIMARY KEY,
  notify_channel BIGINT,
  panel_channel_id BIGINT,
  panel_message_id BIGINT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- slots（無ければ作る）
CREATE TABLE IF NOT EXISTS slots (
  id BIGSERIAL PRIMARY KEY,
  guild_id BIGINT NOT NULL,
  slot_time TEXT NOT NULL,         -- "HH:MM"
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (guild_id, slot_time)
);

-- reservations（無ければ作る）
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
        # ⭐ 先に既存テーブルの修復
        await conn.execute(MIGRATE_SQL)
        # ⭐ その後、無ければ作成
        await conn.execute(CREATE_SQL)
    return pool
