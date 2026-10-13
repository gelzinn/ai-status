import os
import json
import time
import uuid
import signal
import threading
from . import paths

if not paths.IS_WINDOWS:
    import fcntl

CACHE_FILE = str(paths.CACHE_DIR / "usage.json") if paths.IS_WINDOWS else os.path.expanduser("~/.cache/ai-status.json")
SELECTED_FILE = str(paths.CONFIG_DIR / "selected.json")

LOCK_FILE = str(paths.RUNTIME_DIR / "ai-status-query.lock")
PID_FILE = str(paths.RUNTIME_DIR / "ai-status.pids")
REFRESH_FILE = str(paths.RUNTIME_DIR / "ai-status-refresh.json")

ICON_MODES = ["off", "bot", "logo"]
USAGE_DISPLAY_MODES = ["used", "remaining"]
REFRESH_INTERVAL_MINUTES = tuple(range(5, 61, 5))
DEFAULT_REFRESH_INTERVAL_MINUTES = 5
_lock_heartbeat = None


def _keep_lock_alive(stop):
    # Many account connections may take longer than the stale-lock timeout.
    # Renew while this process owns the refresh so another frontend cannot
    # start a duplicate batch just because the first one is still running.
    while not stop.wait(20):
        try:
            with open(LOCK_FILE, encoding="utf-8") as stream:
                if stream.read().strip() != str(os.getpid()):
                    return
            os.utime(LOCK_FILE, None)
        except OSError:
            return

def get_icon_mode(selected):
    if not selected:
        return "bot"
    mode = selected.get("icon_mode")
    if mode in ICON_MODES:
        return mode
    return "bot" if selected.get("show_icon", True) else "off"


def get_usage_display(selected):
    mode = (selected or {}).get("usage_display")
    return mode if mode in USAGE_DISPLAY_MODES else "used"


def validate_refresh_interval_minutes(value):
    if type(value) is not int or value not in REFRESH_INTERVAL_MINUTES:
        raise ValueError("Choose a refresh interval from 5 to 60 minutes in steps of 5.")
    return value


def get_refresh_interval_minutes(selected=None):
    try:
        return validate_refresh_interval_minutes((selected or {}).get("refresh_interval_minutes"))
    except (ValueError, AttributeError):
        return DEFAULT_REFRESH_INTERVAL_MINUTES


def get_refresh_interval_seconds(selected=None):
    return get_refresh_interval_minutes(selected) * 60

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
    global _lock_heartbeat
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        if os.path.exists(LOCK_FILE):
            mtime = os.path.getmtime(LOCK_FILE)
            if time.time() - mtime < 90:
                return False
            os.remove(LOCK_FILE)
        with open(LOCK_FILE, "x") as f:
            f.write(str(os.getpid()))
        if _lock_heartbeat is not None:
            _lock_heartbeat.set()
        _lock_heartbeat = threading.Event()
        threading.Thread(target=_keep_lock_alive, args=(_lock_heartbeat,), daemon=True).start()
        return True
    except Exception:
        return False

def release_lock():
    global _lock_heartbeat
    if _lock_heartbeat is not None:
        _lock_heartbeat.set()
        _lock_heartbeat = None
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
