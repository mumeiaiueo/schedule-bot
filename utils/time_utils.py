from datetime import datetime, timedelta

def generate_slots(start, end, interval):
    slots = []
    now = start
    while now < end:
        slots.append(now.strftime("%H:%M"))
        now += timedelta(minutes=interval)
    return slots
