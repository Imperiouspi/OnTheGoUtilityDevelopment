import json
import os
import copy

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Positions: 0=right, going clockwise: 1=bottom-right, 2=bottom, 3=bottom-left,
# 4=left, 5=top-left, 6=top, 7=top-right
POSITION_NAMES = [
    "right", "bottom-right", "bottom", "bottom-left",
    "left", "top-left", "top", "top-right"
]

TOP_RIGHT_INDEX = 7


def _empty_slot():
    return {"label": "Select to add action", "type": None, "value": None}


def _back_slot():
    return {"label": "Back", "type": "back", "value": None}


def default_config():
    return {
        "root": {
            "slots": [_empty_slot() for _ in range(8)]
        }
    }


def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = default_config()
        save_config(cfg)
        return cfg
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def get_folder(cfg, path):
    """Get a folder by path. path is a list like [] for root, or ["subfolder_id"]."""
    if not path:
        return cfg["root"]
    folder_id = path[-1]
    if folder_id in cfg:
        return cfg[folder_id]
    return None


def create_subfolder(cfg, folder_id):
    """Create a new subfolder and return its id."""
    slots = [_empty_slot() for _ in range(8)]
    slots[TOP_RIGHT_INDEX] = _back_slot()
    cfg[folder_id] = {"slots": slots}
    save_config(cfg)
    return cfg[folder_id]


def set_slot(cfg, folder_path, slot_index, action_type, value, label=None):
    """Set an action for a slot."""
    folder = get_folder(cfg, folder_path)
    if folder is None:
        return

    if action_type == "folder":
        folder_id = f"folder_{id(value) if value else os.urandom(4).hex()}"
        if label is None:
            label = value if isinstance(value, str) else "Folder"
        folder["slots"][slot_index] = {
            "label": label,
            "type": "folder",
            "value": folder_id
        }
        create_subfolder(cfg, folder_id)
    else:
        if label is None:
            label = str(value)
        folder["slots"][slot_index] = {
            "label": label,
            "type": action_type,
            "value": value
        }
    save_config(cfg)
