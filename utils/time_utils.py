from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))


# ===== 基本 =====

def jst_now() -> datetime:
    return datetime.now(JST)


def ymd_jst(d: datetime) -> str:
    return d.astimezone(JST).strftime("%Y-%m-%d")


# ===== 時刻変換 =====

def hm_to_minutes(hm: str) -> int:
    """
    "HH:MM" → 分(int)
    """
    if not hm:
        return 0
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def minutes_to_hm(x: int) -> str:
    """
    分(int) → "HH:MM"
    """
    h = x // 60
    m = x % 60
    return f"{h:02d}:{m:02d}"


# ===== Select用（25件制限対応） =====

def hour_options() -> list[str]:
    """
    00〜23（24件）
    Discord Select上限25以内OK
    """
    return [f"{h:02d}" for h in range(24)]


def minute_options(step: int = 5) -> list[str]:
    """
    00〜59（step刻み）
    step=5 → 12件
    """
    return [f"{m:02d}" for m in range(0, 60, step)]