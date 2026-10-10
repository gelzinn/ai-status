import os
import json
import time
import fcntl
import tempfile

CACHE_FILE = os.path.expanduser("~/.cache/ai-status.json")
SELECTED_FILE = os.path.expanduser("~/.config/ai-status/selected.json")

LOCK_FILE = "/tmp/ai-status-query.lock"
PID_FILE = "/tmp/ai-status.pids"

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
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def _save_json(path, data):
    """Atomic publication for frontends reading shared state concurrently."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as f:
            temporary = f.name
            json.dump(data, f)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)

def save_cache(data):
    try:
        _save_json(CACHE_FILE, data)
    except Exception:
        pass

def acquire_lock():
    try:
        if os.path.exists(LOCK_FILE):
            mtime = os.path.getmtime(LOCK_FILE)
            if time.time() - mtime < 15:
                return False
        with open(LOCK_FILE, "w") as f:
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
            with open(SELECTED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_selected(data):
    try:
        _save_json(SELECTED_FILE, data)
    except Exception:
        pass

def trigger_refresh():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, "r") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                lines = f.readlines()
            for line in lines:
                try:
                    pid = int(line.strip())
                    os.kill(pid, 10) # SIGUSR1
                except (ValueError, OSError):
                    pass
        except Exception:
            pass
