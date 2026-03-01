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

def make_time_options(step_min=5):
    opts = []
    for t in range(0, 24 * 60, step_min):
        opts.append(minutes_to_hm(t))
    return opts