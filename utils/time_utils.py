from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

def parse_hhmm(text: str) -> tuple[int, int]:
    t = text.strip()
    dt = datetime.strptime(t, "%H:%M")
    return dt.hour, dt.minute

def build_slots(start_hhmm: str, end_hhmm: str, interval: int) -> list[dict]:
    if interval not in (20, 25, 30):
        raise ValueError("interval must be 20/25/30")

    sh, sm = parse_hhmm(start_hhmm)
    eh, em = parse_hhmm(end_hhmm)

    now = datetime.now(JST)
    base_date = now.date()

    start = datetime(base_date.year, base_date.month, base_date.day, sh, sm, tzinfo=JST)
    end   = datetime(base_date.year, base_date.month, base_date.day, eh, em, tzinfo=JST)

    # 日付またぎ
    if end <= start:
        end += timedelta(days=1)

    slots = []
    cur = start
    while cur + timedelta(minutes=interval) <= end:
        nxt = cur + timedelta(minutes=interval)
        slot_id = cur.isoformat()  # 一意ID（日付含む）
        slots.append({
            "id": slot_id,
            "start_iso": cur.isoformat(),
            "end_iso": nxt.isoformat()
        })
        cur = nxt

    return slots
