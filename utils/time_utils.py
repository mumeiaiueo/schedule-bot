from datetime import datetime, timedelta, timezone, date

JST = timezone(timedelta(hours=9))

def jst_now() -> datetime:
    return datetime.now(JST)

def jst_today() -> date:
    return jst_now().date()

def day_from_key(day_key: str) -> date:
    # "today" / "tomorrow"
    base = jst_today()
    if day_key == "tomorrow":
        return base + timedelta(days=1)
    return base

def hm_to_minutes(hm: str) -> int:
    h, m = hm.split(":")
    return int(h) * 60 + int(m)

def hour_options():
    return [f"{h:02d}" for h in range(24)]  # 24件

def minute_options(step=5):
    return [f"{m:02d}" for m in range(0, 60, step)]  # 12件

def build_dt(day: date, hh: str, mm: str) -> datetime:
    return datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=JST)

def build_hm(hh: str | None, mm: str | None) -> str | None:
    if not hh or not mm:
        return None
    return f"{hh}:{mm}"