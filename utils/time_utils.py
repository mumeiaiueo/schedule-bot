from datetime import datetime, timedelta, timezone, date

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

# Select用（25件以内）
def hour_options():
    return [f"{h:02d}" for h in range(24)]  # 24件

def minute_options(step=5):
    return [f"{m:02d}" for m in range(0, 60, step)]  # 最大12件

def day_key_to_date(day_key: str) -> date:
    today = jst_now().date()
    if day_key == "tomorrow":
        return today + timedelta(days=1)
    return today

def make_dt_from_hm(day_key: str, hh: str, mm: str) -> datetime:
    d = day_key_to_date(day_key)
    return datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=JST)