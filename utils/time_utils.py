from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

def jst_now() -> datetime:
    return datetime.now(JST)

def ymd_jst(d: datetime) -> str:
    return d.astimezone(JST).strftime("%Y-%m-%d")

def hm_to_minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)

def minutes_to_hm(x: int) -> str:
    h = x // 60
    m = x % 60
    return f"{h:02d}:{m:02d}"

# ✅ 追加（Select用：25件以内にするため）
def hour_options():
    return [f"{h:02d}" for h in range(24)]  # 24件

def minute_options(step=5):
    return [f"{m:02d}" for m in range(0, 60, step)]  # 最大12件