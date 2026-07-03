import os
import time
import json
import signal
import sys
import threading
from . import state
from . import fetch
from . import render
from . import config as cfgmod

should_update = True
is_updating = False
latest_data = []

def update_task():
    global latest_data, is_updating
    try:
        if state.acquire_lock():
            try:
                data = fetch.fetch_all_data()
                if data:
                    latest_data = data
                    state.save_cache(data)
            finally:
                state.release_lock()
        else:
            start_wait = time.time()
            while time.time() - start_wait < 15:
                time.sleep(0.5)
                if not os.path.exists(state.LOCK_FILE):
                    break
            latest_data = state.load_cache()
    except Exception:
        pass
    finally:
        is_updating = False

def handle_signal(signum, frame):
    global should_update
    should_update = True

def run():
    global should_update, is_updating, latest_data
    
    state.register_pid()
    signal.signal(signal.SIGUSR1, handle_signal)
    latest_data = state.load_cache()
    
    last_auto_update = time.time()
    last_update_check = 0
    last_config_mtime = 0
    should_update = True
    
    while True:
        try:
            now = time.time()
            
            if now - last_update_check >= 3600:
                fetch.check_for_updates()
                last_update_check = now
            
            config_mtime = 0
            if os.path.exists(cfgmod.CONFIG_FILE):
                config_mtime = os.path.getmtime(cfgmod.CONFIG_FILE)
            if config_mtime != last_config_mtime:
                last_config_mtime = config_mtime
                should_update = True
                
            if should_update and not is_updating:
                should_update = False
                is_updating = True
                
                t = threading.Thread(target=update_task)
                t.start()
                
                frame = 0
                while is_updating:
                    output = render.build_loading_state(latest_data, frame)
                    print(json.dumps(output, ensure_ascii=False), flush=True)
                    frame += 1
                    time.sleep(0.15)
                    
                output = render.build_final_state(latest_data)
                print(json.dumps(output, ensure_ascii=False), flush=True)
                last_auto_update = now
                
            time.sleep(1)
            if now - last_auto_update >= 300:
                should_update = True
                
        except KeyboardInterrupt:
            break
        except Exception:
            time.sleep(5)
