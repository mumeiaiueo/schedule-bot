# utils/db.py
import os
from supabase import create_client

sb = None

def init_supabase():
    global sb

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    print("SUPABASE_URL set? =", bool(url))
    print("SUPABASE_KEY set? =", bool(key))

    if not url or not key:
        sb = None
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY が未設定です")

    sb = create_client(url, key)
    print("✅ Supabase client created")
    return sb

# ★重要：モジュール読み込み時に必ず初期化（Render起動時に1回だけ走る）
try:
    init_supabase()
except Exception as e:
    print("❌ Supabase init failed:", e)