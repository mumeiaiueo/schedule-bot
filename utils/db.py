# utils/db.py
print("✅ LOADED db.py v2026-02-27 safe-no-proxy (FULL COPY)")

import os
import socket
from urllib.parse import urlparse

from supabase import create_client


def _pick_first_env(*keys: str) -> tuple[str | None, str | None]:
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


SUPABASE_URL, _URL_KEYNAME = _pick_first_env(
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "DATABASE_SUPABASE_URL",
)

SUPABASE_KEY, _KEY_KEYNAME = _pick_first_env(
    "SUPABASE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_ANON_KEY",
)

print(f"SUPABASE_URL key = {_URL_KEYNAME}")
print(f"SUPABASE_KEY key = {_KEY_KEYNAME}")
print(f"SUPABASE_URL set? = {bool(SUPABASE_URL)}")
print(f"SUPABASE_KEY set? = {bool(SUPABASE_KEY)}")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("⚠️ Supabase env is missing. DB features will be disabled.")
    sb = None
else:
    _host = _host_from_url(SUPABASE_URL)
    if _host:
        try:
            ip = socket.gethostbyname(_host)
            print(f"✅ DNS check OK: {_host} -> {ip}")
        except Exception as e:
            print(f"⚠️ DNS check failed for {_host}: {repr(e)}")
    else:
        print("⚠️ Could not parse host from SUPABASE_URL")

    try:
        # proxy 引数は絶対渡さない（環境差で死ぬ）
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client created")
    except Exception as e:
        print("⚠️ Supabase client create failed:", repr(e))
        sb = None