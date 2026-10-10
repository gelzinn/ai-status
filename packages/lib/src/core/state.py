import os
import json
import time
import uuid
import signal
from . import paths

if not paths.IS_WINDOWS:
    import fcntl

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

def _save_json(path, data):
    """Publish shared preferences through the portable atomic writer."""
    paths.atomic_json(path, data)

def save_cache(data):
    try:
        _save_json(CACHE_FILE, data)
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

def _update_pids(register):
    # A widget disappearing must not remove another frontend's refresh target.
    if paths.IS_WINDOWS:
        return
    os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
    try:
        with open(PID_FILE, "a+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            pids = set()
            for line in f:
                try:
                    pid = int(line.strip())
                    os.kill(pid, 0)
                    pids.add(pid)
                except (ValueError, OSError):
                    pass
            if register:
                pids.add(os.getpid())
            else:
                pids.discard(os.getpid())
            f.seek(0)
            f.truncate()
            f.write("".join(f"{pid}\n" for pid in sorted(pids)))
    except OSError:
        pass

def register_pid():
    _update_pids(register=True)

def unregister_pid():
    """Remove this daemon's refresh target when its frontend is unloaded."""
    _update_pids(register=False)

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
        _save_json(SELECTED_FILE, data)
    except Exception:
        pass

def trigger_refresh():
    if paths.IS_WINDOWS:
        paths.atomic_json(REFRESH_FILE, {"request": uuid.uuid4().hex})
        return
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                lines = f.readlines()
            for line in lines:
                try:
                    pid = int(line.strip())
                    os.kill(pid, signal.SIGUSR1)
                except (ValueError, OSError):
                    pass
        except Exception:
            pass
