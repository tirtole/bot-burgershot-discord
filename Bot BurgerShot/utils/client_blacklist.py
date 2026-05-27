from pathlib import Path
from datetime import datetime

from utils.storage import load_json, save_json


BLACKLIST_FILE = Path("data/client_blacklist.json")


def load_blacklist():
    return load_json(BLACKLIST_FILE, {})


def save_blacklist(data):
    save_json(BLACKLIST_FILE, data)


def blacklist_user(guild_id: int, user_id: int, reason: str, staff_id: int):
    data = load_blacklist()
    guild_key = str(guild_id)
    user_key = str(user_id)

    if guild_key not in data:
        data[guild_key] = {}

    data[guild_key][user_key] = {
        "reason": reason or "Aucune raison.",
        "staff_id": staff_id,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M")
    }

    save_blacklist(data)


def unblacklist_user(guild_id: int, user_id: int):
    data = load_blacklist()
    guild_key = str(guild_id)
    user_key = str(user_id)

    if guild_key in data and user_key in data[guild_key]:
        del data[guild_key][user_key]
        save_blacklist(data)
        return True

    return False


def is_user_blacklisted(guild_id: int, user_id: int):
    data = load_blacklist()
    return str(user_id) in data.get(str(guild_id), {})


def get_blacklist_entry(guild_id: int, user_id: int):
    data = load_blacklist()
    return data.get(str(guild_id), {}).get(str(user_id))


def get_guild_blacklist(guild_id: int):
    data = load_blacklist()
    return data.get(str(guild_id), {})