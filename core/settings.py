import json
import os

_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

_DEFAULTS: dict = {
    "daily_goal": 20,
    "due_cards_limit": 50,
    "new_cards_limit": 20,
}


def load() -> dict:
    try:
        with open(_FILE) as f:
            return {**_DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def save(data: dict) -> None:
    merged = {**_DEFAULTS, **data}
    with open(_FILE, "w") as f:
        json.dump(merged, f, indent=2)
