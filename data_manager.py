import json
import os

DATA_FILE = "data.json"


def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_channel(data, channel_id: int):
    channel_id = str(channel_id)

    if channel_id not in data:
        data[channel_id] = {
            "title": "",
            "slots": [],
            "reservations": {},
            "breaks": [],
            "meta": {},
            "panel": {
                "channel_id": None,
                "message_id": None
            }
        }

    return data[channel_id]