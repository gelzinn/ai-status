import os
import json
import time

CACHE_FILE = os.path.expanduser("~/.cache/ai-status.json")
LOCK_FILE = "/tmp/ai-status-query.lock"
PID_FILE = "/tmp/ai-status.pids"
SELECTED_FILE = os.path.expanduser("~/.config/ai-status/selected.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
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

def register_pid():
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
            with open(SELECTED_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return None

def save_selected(data):
    try:
        os.makedirs(os.path.dirname(SELECTED_FILE), exist_ok=True)
        with open(SELECTED_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

def trigger_refresh():
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
