from datetime import datetime, timedelta, date, time as dtime
import pytz

JST = pytz.timezone("Asia/Tokyo")

def jst_now() -> datetime:
    return datetime.now(tz=JST)

def jst_today_date(offset_days: int = 0) -> date:
    return (jst_now() + timedelta(days=offset_days)).date()

def parse_hm(s: str):
    hh, mm = s.split(":")
    return int(hh), int(mm)

def build_range_jst(day_date: date, sh: int, sm: int, eh: int, em: int):
    start_dt = JST.localize(datetime.combine(day_date, dtime(sh, sm)))

    # 24:00対応
    if eh == 24 and em == 0:
        end_dt = JST.localize(datetime.combine(day_date + timedelta(days=1), dtime(0, 0)))
        return start_dt, end_dt

    end_dt = JST.localize(datetime.combine(day_date, dtime(eh, em)))

    # 日跨ぎ（例：23:00-01:00）
    if end_dt <= start_dt:
        end_dt = end_dt + timedelta(days=1)

    return start_dt, end_dt

def to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(pytz.utc).isoformat()

def from_utc_iso(s: str) -> datetime:
    s2 = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s2).astimezone(JST)

def fmt_hm(dt: datetime) -> str:
    return dt.astimezone(JST).strftime("%H:%M")