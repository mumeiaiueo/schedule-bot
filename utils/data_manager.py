import json
import os

DATA_PATH = os.path.join("data", "data.json")

def load_data():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"guilds": {}}

def save_data(data):
    os.makedirs("data", exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild(data, guild_id: int):
    gid = str(guild_id)
    if gid not in data["guilds"]:
        data["guilds"][gid] = {
            "notify_channel": None,
            "panel": {
                "channel_id": None,
                "message_id": None
            },
            "slots": [],
            "reservations": {},   # {"12:50": user_id}
            "reminded": []        # ["12:50"] 送信済み
        }
    return data["guilds"][gid]
