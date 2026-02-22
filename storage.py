import json
import os

FILE = "data.json"

def load():
    if not os.path.exists(FILE):
        return {"reservations": {}, "notify": {}}
    with open(FILE, "r") as f:
        return json.load(f)

def save(data):
    with open(FILE, "w") as f:
        json.dump(data, f, indent=2)
