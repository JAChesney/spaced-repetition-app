import json
import os

_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "settings.json")

_DEFAULTS: dict = {
    "session_size": 100,
}


def load() -> dict:
    try:
        with open(_FILE) as f:
            stored = json.load(f)
        merged = {**_DEFAULTS, **stored}
        # Migrate legacy keys
        if "session_size" not in stored:
            legacy = stored.get("session_limit") or stored.get("due_cards_limit", 100)
            merged["session_size"] = max(1, int(legacy))
        return merged
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(_DEFAULTS)


def save(data: dict) -> None:
    merged = {**_DEFAULTS, **data}
    with open(_FILE, "w") as f:
        json.dump(merged, f, indent=2)
