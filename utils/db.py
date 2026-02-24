import os
import socket
from urllib.parse import urlparse

from supabase import create_client


def _pick_first_env(*keys: str) -> tuple[str | None, str | None]:
    """
    指定した環境変数名を順に探して、最初に見つかった値とそのキー名を返す
    """
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


# ---- URL ----
# 互換用に複数キー候補を許可
SUPABASE_URL, _URL_KEYNAME = _pick_first_env(
    "SUPABASE_URL",
    "SUPABASE_PROJECT_URL",
    "DATABASE_SUPABASE_URL",
)

# ---- KEY ----
# あなたの会話の流れ的に、Render側には SUPABASE_KEY を置く運用が一番ラク。
# ただし既存の SUPABASE_SERVICE_ROLE_KEY も拾えるようにする。
SUPABASE_KEY, _KEY_KEYNAME = _pick_first_env(
    "SUPABASE_KEY",               # ★おすすめ（これ1本に揃える）
    "SUPABASE_SERVICE_ROLE_KEY",  # 既存互換
    "SUPABASE_ANON_KEY",          # 万一の互換（RLS運用なら）
)

# ---- バリデーション ----
if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL が未設定です（RenderのEnvironmentに SUPABASE_URL を追加してください）"
    )

if not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_KEY が未設定です（RenderのEnvironmentに SUPABASE_KEY を追加してください）"
    )

# ---- どの環境変数から取ったかをログに出す（値は出さない）----
print(f"SUPABASE_URL key = {_URL_KEYNAME}")
print(f"SUPABASE_URL = '{SUPABASE_URL}'")
print(f"SUPABASE_KEY key = {_KEY_KEYNAME}")
print("SUPABASE_KEY set? = True")  # 値は絶対表示しない

# ---- DNSチェック（失敗しても即死させない。原因切り分け用）----
_host = _host_from_url(SUPABASE_URL)
if _host:
    try:
        ip = socket.gethostbyname(_host)
        print(f"✅ DNS check OK: {_host} -> {ip}")
    except Exception as e:
        # ここが出るなら Render側のDNS/ネット不調 or URL typo の可能性が高い
        print(f"⚠️ DNS check failed for {_host}: {repr(e)}")
else:
    print("⚠️ Could not parse host from SUPABASE_URL")

# ---- client 作成 ----
# ここで create_client が失敗するなら「URLかKEYがおかしい」か「ネットワーク/DNS」。
sb = create_client(SUPABASE_URL, SUPABASE_KEY)
print("✅ Supabase client created")