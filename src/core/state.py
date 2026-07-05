import os
import json
import time
import sys

if sys.platform == "darwin":
    _cache_dir = os.path.expanduser("~/Library/Caches/ai-status")
    _config_dir = os.path.expanduser("~/Library/Application Support/ai-status")
else:
    _cache_dir = os.path.expanduser("~/.cache/ai-status")
    _config_dir = os.path.expanduser("~/.config/ai-status")

CACHE_FILE = os.path.join(_cache_dir, "status.json")
LOCK_FILE = os.path.join(_cache_dir, "query.lock")
PID_FILE = os.path.join(_cache_dir, "pids")
SELECTED_FILE = os.path.join(_config_dir, "selected.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return []

def save_cache(data):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
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
    except OSError:
        return False

def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except OSError:
        pass

def register_pid():
    pids = []
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                for line in f:
                    try:
                        pid = int(line.strip())
                        os.kill(pid, 0)
                        pids.append(pid)
                    except (ValueError, OSError):
                        pass
        except OSError:
            pass
    my_pid = os.getpid()
    if my_pid not in pids:
        pids.append(my_pid)
    try:
        with open(PID_FILE, "w") as f:
            for pid in pids:
                f.write(f"{pid}\n")
    except OSError:
        pass

def load_selected():
    if os.path.exists(SELECTED_FILE):
        try:
            with open(SELECTED_FILE) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return None

def save_selected(data):
    try:
        os.makedirs(os.path.dirname(SELECTED_FILE), exist_ok=True)
        with open(SELECTED_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass

def trigger_refresh():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                for line in f:
                    try:
                        pid = int(line.strip())
                        os.kill(pid, 10)
                    except (ValueError, OSError):
                        pass
        except OSError:
            pass
