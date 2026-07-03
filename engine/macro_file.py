import json

from engine.actions import action_from_dict

# Every saved macro is a JSON object with this wrapper so a file can be
# recognised as ours (and rejected early if it isn't) and so the format can
# be versioned later without guessing at a bare list of actions.
MACRO_FORMAT = "macro"
MACRO_VERSION = 1

MACRO_EXTENSION = ".json"
MACRO_FILE_FILTER = "JSON Files (*.json);;All Files (*)"


def save_macro(path: str, actions: list) -> None:
    """Serialize a list of action objects to a JSON macro file at `path`."""
    payload = {
        "format": MACRO_FORMAT,
        "version": MACRO_VERSION,
        "actions": [action.to_dict() for action in actions],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_macro(path: str) -> list:
    """Load a macro file and return the reconstructed list of action objects.

    Raises OSError if the file can't be read and ValueError (which
    json.JSONDecodeError subclasses) if it isn't a valid macro file."""
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, dict) or payload.get("format") != MACRO_FORMAT:
        raise ValueError("This file isn't a valid macro file.")

    actions_data = payload.get("actions")
    if not isinstance(actions_data, list):
        raise ValueError("Macro file is missing its list of actions.")

    return [action_from_dict(entry) for entry in actions_data]
