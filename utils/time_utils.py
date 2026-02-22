from datetime import datetime, timedelta

def generate_slots(start_hm: str, end_hm: str, interval: int):
    # start_hm/end_hm: "HH:MM"
    start = datetime.strptime(start_hm, "%H:%M")
    end = datetime.strptime(end_hm, "%H:%M")

    # 同日基準で比較（end<=startなら翌日扱い）
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_dt = base.replace(hour=start.hour, minute=start.minute)
    end_dt = base.replace(hour=end.hour, minute=end.minute)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    slots = []
    cur = start_dt
    while cur + timedelta(minutes=interval) <= end_dt:
        slots.append(cur.strftime("%H:%M"))
        cur += timedelta(minutes=interval)
    return slots
