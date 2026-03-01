from datetime import datetime, timezone, timedelta
import pytz

JST = pytz.timezone("Asia/Tokyo")


def jst_now():
    return datetime.now(JST)


def to_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def from_utc_iso(s: str) -> datetime:
    return datetime.fromisoformat(s).astimezone(JST)


def fmt_hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")