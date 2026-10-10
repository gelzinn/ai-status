import os
import json
from . import paths

CONFIG_DIR = str(paths.CONFIG_DIR)
CONFIG_FILE = os.path.join(CONFIG_DIR, "providers.json")

def providers_dir():
    return str(paths.PROVIDERS_DIR)

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
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_config(order):
    paths.atomic_json(CONFIG_FILE, order)

def enabled_order():
    cfg = load_config()
    if isinstance(cfg, list):
        return cfg
    return available_providers()
