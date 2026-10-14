import os
import json
from . import paths
from . import accounts

CONFIG_DIR = str(paths.CONFIG_DIR)
CONFIG_FILE = os.path.join(CONFIG_DIR, "providers.json")
# Metered API connections require explicit setup; keep existing installations'
# automatic CLI/session discovery when no providers.json has been saved.
DEFAULT_PROVIDERS = ("antigravity", "claude", "codex", "commandcode", "copilot", "kiro", "opencode", "zai")

def providers_dir():
    return str(paths.PROVIDERS_DIR)

def available_providers():
    d = providers_dir()
    try:
        # DirEntry reuses directory metadata on Windows instead of issuing a
        # separate stat call for every provider on every settings update.
        with os.scandir(d) as entries:
            return sorted(p.name for p in entries if not p.name.startswith("__") and p.is_dir())
    except (FileNotFoundError, NotADirectoryError):
        return []

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
    return [name for name in available_providers() if name in DEFAULT_PROVIDERS]


def accounts_file():
    return os.path.join(os.path.dirname(CONFIG_FILE), "accounts.json")


def load_accounts():
    return accounts.load_document(accounts_file())["accounts"]


def available_connections():
    """Stable IDs for settings, including disabled saved account connections."""
    return available_providers() + ["account:" + record["id"] for record in load_accounts()]


def connection_info(identity):
    if not isinstance(identity, str):
        return None
    if identity.startswith("account:"):
        account_id = identity[len("account:"):]
        for record in load_accounts():
            if record["id"] == account_id:
                return accounts.connection(record)
        return None
    if identity in available_providers():
        return {"connection_id": identity, "provider": identity, "account_id": None,
                "label": identity, "enabled": identity in enabled_order(), "env": {}, "options": {}}
    return None


def enabled_connection_order():
    document = accounts.load_document(accounts_file())
    available = set(available_providers())
    enabled = list(dict.fromkeys(name for name in enabled_order()
                                if isinstance(name, str) and name in available))
    enabled += ["account:" + record["id"] for record in document["accounts"] if record["enabled"]]
    order = document.get("order", [])
    return [identity for identity in order if identity in enabled] + [identity for identity in enabled if identity not in order]


def enabled_connections():
    document = accounts.load_document(accounts_file())
    records = {"account:" + record["id"]: accounts.connection(record) for record in document["accounts"]}
    return [records[identity] if identity in records else {
        "connection_id": identity, "provider": identity, "account_id": None,
        "label": identity, "enabled": True, "env": {}, "options": {},
    } for identity in enabled_connection_order()]


def save_connection_order(identities):
    """Persist settings without deleting disabled accounts or credential refs."""
    if not isinstance(identities, list) or any(not isinstance(identity, str) for identity in identities):
        raise ValueError("Connection order must be a list of connection IDs.")
    available = set(available_connections())
    if len(set(identities)) != len(identities) or any(identity not in available for identity in identities):
        raise ValueError("Connection order contains an unknown or duplicate connection.")
    document = accounts.load_document(accounts_file())
    selected = set(identities)
    for record in document["accounts"]:
        record["enabled"] = "account:" + record["id"] in selected
    document["order"] = list(identities)
    if document["accounts"] or os.path.exists(accounts_file()):
        accounts.save_document(document, accounts_file())
    save_config([identity for identity in identities if not identity.startswith("account:")])
