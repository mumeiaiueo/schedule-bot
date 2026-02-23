import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

print("SUPABASE_URL =", repr(SUPABASE_URL))
print("SUPABASE_KEY set? =", bool(SUPABASE_KEY))

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL が未設定です")
if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY が未設定です")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Supabase client created")