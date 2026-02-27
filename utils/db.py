# utils/db.py
import os
import socket
from urllib.parse import urlparse

from supabase import create_client


def _pick_first_env(*keys: str) -> tuple[str | None, str | None]:
    """指定した環境変数名を順に探して、最初に見つかった値とそのキー名を返す"""
    for k in keys:
        v = os.getenv(k)
        if v and str(v).strip():
            return str(v).strip(), k
    return None, None


def _host_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except Exception:
        return None


# ---- URL（互換で複数キー候補）----
SUPABASE_URL, _URL_KEYNAME = _pick_first_env(
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "DATABASE_SUPABASE_URL",
)

# ---- KEY（おすすめは SUPABASE_KEY に統一）----
SUPABASE_KEY, _KEY_KEYNAME = _pick_first_env(
    "SUPABASE_KEY",               # ★これに統一するのが楽
    "SUPABASE_SERVICE_ROLE_KEY",  # 既存互換
    "SUPABASE_ANON_KEY",          # 互換（RLS運用なら）
)

# ---- どの環境変数から取ったか（値は絶対出さない）----
print(f"SUPABASE_URL key = {_URL_KEYNAME}")
print(f"SUPABASE_KEY key = {_KEY_KEYNAME}")
print(f"SUPABASE_URL set? = {bool(SUPABASE_URL)}")
print(f"SUPABASE_KEY set? = {bool(SUPABASE_KEY)}")

# ---- バリデーション（ここでは “落とさない” 方針）----
if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Supabase env is missing. DB features will be disabled.")
    sb = None
else:
    # ---- DNSチェック（落とさない）----
    _host = _host_from_url(SUPABASE_URL)
    if _host:
        try:
            ip = socket.gethostbyname(_host)
            print(f"✅ DNS check OK: {_host} -> {ip}")
        except Exception as e:
            print(f"⚠️ DNS check failed for {_host}: {repr(e)}")
    else:
        print("⚠️ Could not parse host from SUPABASE_URL")

    # ---- client 作成（ここも落とさない）----
    try:
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client created")
    except Exception as e:
        print("⚠️ Supabase client create failed:", repr(e))
        sb = None