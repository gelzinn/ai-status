import os
import time
import json
import signal
import sys
import threading
from . import state
from . import fetch
from . import render
from . import logos
from . import config as cfgmod

should_update = True
is_updating = False
latest_data = []

# Streaming fetch state: update_task fills these per provider as results arrive,
# and the render loop reads them so each provider shows its own loading state and
# the selected one appears the moment it's ready (not after the slowest one).
_results_by_dir = {}
_pending = set()


def _group_by_dir(data):
    groups = {}
    for p in (data or []):
        groups.setdefault(p.get("_dir"), []).append(p)
    return groups


def _ordered_merged(order):
    out = []
    for name in order:
        entries = _results_by_dir.get(name)
        if entries:
            out.extend(entries)
    return out


def update_task():
    global latest_data, is_updating
    try:
        if state.acquire_lock():
            try:
                def on_result(dir_name, providers):
                    if providers:
                        _results_by_dir[dir_name] = providers
                    _pending.discard(dir_name)

                data = fetch.fetch_all_data(on_result=on_result)
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
        _pending.clear()
        is_updating = False

def handle_signal(signum, frame):
    global should_update
    should_update = True

def run():
    global should_update, is_updating, latest_data, _results_by_dir, _pending

    state.register_pid()
    signal.signal(signal.SIGUSR1, handle_signal)
    latest_data = state.load_cache()

    if not state.load_selected():
        for p in latest_data:
            if p.get("metrics"):
                state.save_selected({"provider": p["_dir"], "idx": p.get("_idx", 0), "metric": "rolling"})
                break
        else:
            providers = cfgmod.enabled_order()
            if providers:
                state.save_selected({"provider": providers[0], "idx": 0, "metric": "rolling"})

    # Seed the waybar logo (current.png) for the selected provider on startup.
    logos.update_current(state.load_selected())

    last_auto_update = time.time()
    last_update_check = 0
    last_config_mtime = 0
    last_selected_mtime = 0
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

            selected_mtime = 0
            if os.path.exists(state.SELECTED_FILE):
                selected_mtime = os.path.getmtime(state.SELECTED_FILE)
            
            selected = state.load_selected()
            
            if should_update and not is_updating:
                should_update = False
                is_updating = True

                # Seed streaming state: start from the cached data (so each
                # provider animates its previous value) and mark every enabled
                # provider pending until its fresh result arrives.
                order = cfgmod.enabled_order()
                _results_by_dir = _group_by_dir(latest_data)
                _pending = set(order)

                t = threading.Thread(target=update_task)
                t.start()

                frame = 0
                while is_updating:
                    merged = _ordered_merged(order)
                    output = render.build_loading_state(
                        merged, frame, selected, pending=_pending
                    )
                    print(json.dumps(output, ensure_ascii=False), flush=True)
                    frame += 1
                    time.sleep(0.15)

                output = render.build_final_state(latest_data, selected)
                print(json.dumps(output, ensure_ascii=False), flush=True)
                last_auto_update = now
                last_selected_mtime = selected_mtime

            # Re-render on scroll (selected file changed, no re-fetch needed).
            # Polled at a short interval so the text/percentage follow the logo
            # (which the scroll command updates instantly) without a visible lag.
            elif selected_mtime != last_selected_mtime and not is_updating:
                last_selected_mtime = selected_mtime
                output = render.build_final_state(latest_data, selected)
                print(json.dumps(output, ensure_ascii=False), flush=True)
                logos.update_current(selected)

            time.sleep(0.1)
            if now - last_auto_update >= 300:
                should_update = True
                
        except KeyboardInterrupt:
            break
        except BrokenPipeError:
            break
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            time.sleep(5)
