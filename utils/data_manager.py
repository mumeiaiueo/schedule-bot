import json
import os

DATA_PATH = "data/data.json"

def _ensure_file():
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)

def load_data() -> dict:
    _ensure_file()
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(data: dict) -> None:
    _ensure_file()
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild(data: dict, guild_id: int) -> dict:
    g = data.setdefault("guilds", {})
    return g.setdefault(str(guild_id), {
        "remind_channel_id": None,
        "panel_channel_id": None,
        "panel_message_id": None,
        "slots": [],          # [{id, start_iso, end_iso}]
        "reservations": {},   # {slot_id: user_id}
        "reminded": []        # [slot_id]
    })
