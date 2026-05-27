import json
from pathlib import Path


def load_json(path: Path, default_data):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        save_json(path, default_data)
        return default_data

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)