import os
import json
import sys

if sys.platform == "darwin":
    CONFIG_DIR = os.path.expanduser("~/Library/Application Support/ai-status")
else:
    CONFIG_DIR = os.path.expanduser("~/.config/ai-status")
CONFIG_FILE = os.path.join(CONFIG_DIR, "providers.json")


def providers_dir():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "providers"
    )


def available_providers():
    d = providers_dir()
    if not os.path.isdir(d):
        return []
    return sorted(
        p for p in os.listdir(d)
        if os.path.isdir(os.path.join(d, p)) and not p.startswith("__")
    )


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return None


def save_config(order):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(order, f, indent=2)


def enabled_order():
    cfg = load_config()
    if cfg is not None and isinstance(cfg, list) and len(cfg) > 0:
        return cfg
    return available_providers()
