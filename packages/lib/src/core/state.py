import os
import json
import time
import uuid
from . import paths

CACHE_FILE = str(paths.CACHE_DIR / "usage.json") if paths.IS_WINDOWS else os.path.expanduser("~/.cache/ai-status.json")
SELECTED_FILE = str(paths.CONFIG_DIR / "selected.json")

LOCK_FILE = str(paths.RUNTIME_DIR / "ai-status-query.lock")
PID_FILE = str(paths.RUNTIME_DIR / "ai-status.pids")
REFRESH_FILE = str(paths.RUNTIME_DIR / "ai-status-refresh.json")

ICON_MODES = ["off", "bot", "logo"]

def get_icon_mode(selected):
    if not selected:
        return "bot"
    mode = selected.get("icon_mode")
    if mode in ICON_MODES:
        return mode
    return "bot" if selected.get("show_icon", True) else "off"

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception:
            pass
    return []

def save_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        paths.atomic_json(CACHE_FILE, data)
    except Exception:
        pass

def acquire_lock():
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        if os.path.exists(LOCK_FILE):
            mtime = os.path.getmtime(LOCK_FILE)
            if time.time() - mtime < 90:
                return False
            os.remove(LOCK_FILE)
        with open(LOCK_FILE, "x") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return False

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass

def register_pid():
    if paths.IS_WINDOWS:
        return  # os.kill(pid, 0) is not a safe Unix-style liveness probe here.
    pids = []
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                for line in f:
                    try:
                        pid = int(line.strip())
                        os.kill(pid, 0)
                        pids.append(pid)
                    except (ValueError, OSError):
                        pass
        except Exception:
            pass
    my_pid = os.getpid()
    if my_pid not in pids:
        pids.append(my_pid)
    try:
        with open(PID_FILE, "w") as f:
            for pid in pids:
                f.write(f"{pid}\n")
    except Exception:
        pass

def load_selected():
    if os.path.exists(SELECTED_FILE):
        try:
            with open(SELECTED_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else None
        except Exception:
            pass
    return None

def save_selected(data):
    try:
        os.makedirs(os.path.dirname(SELECTED_FILE), exist_ok=True)
        paths.atomic_json(SELECTED_FILE, data)
    except Exception:
        pass

def trigger_refresh():
    if paths.IS_WINDOWS:
        paths.atomic_json(REFRESH_FILE, {"request": uuid.uuid4().hex})
        return
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                for line in f:
                    try:
                        pid = int(line.strip())
                        os.kill(pid, 10) # SIGUSR1
                    except (ValueError, OSError):
                        pass
        except Exception:
            pass
