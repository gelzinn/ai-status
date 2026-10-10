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
from . import quickshell
from . import paths

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
        groups.setdefault(render.connection_key(p), []).append(p)
    return groups


def _ordered_merged(order):
    out = []
    for name in order:
        entries = _results_by_dir.get(name)
        if entries:
            out.extend(entries)
    return out


def update_task(output_format="waybar"):
    global latest_data, is_updating
    try:
        if state.acquire_lock():
            try:
                def on_result(dir_name, providers):
                    if providers:
                        _results_by_dir[dir_name] = providers
                    elif output_format == "quickshell":
                        _results_by_dir.pop(dir_name, None)
                    if output_format == "quickshell":
                        # Clicks must be able to select newly streamed metrics
                        # while another provider is still being queried.
                        state.save_cache(_ordered_merged(cfgmod.enabled_connection_order()))
                    _pending.discard(dir_name)

                data = fetch.fetch_all_data(on_result=on_result, include_errors=output_format == "quickshell")
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

def _run(output_format="waybar"):
    global should_update, is_updating, latest_data, _results_by_dir, _pending

    latest_data = state.load_cache()

    if not state.load_selected():
        for p in latest_data:
            if p.get("metrics"):
                state.save_selected({"provider": render.connection_key(p), "idx": p.get("_idx", 0), "metric": "rolling"})
                break
        else:
            providers = cfgmod.enabled_connection_order()
            if providers:
                state.save_selected({"provider": providers[0], "idx": 0, "metric": "rolling"})

    # Seed the waybar logo (current.png) for the selected provider on startup.
    if output_format == "waybar":
        logos.update_current(state.load_selected())

    logo_cache = quickshell.LogoCache() if output_format == "quickshell" else None
    last_snapshot = None

    def emit(data, selected, frame=None):
        nonlocal last_snapshot
        if output_format == "quickshell":
            logo_paths = {name: logo_cache.get(name) for name in cfgmod.available_providers()}
            logo = logo_paths.get((cfgmod.connection_info(selected.get("provider", "")) or {}).get("provider", ""), "") if state.get_icon_mode(selected) == "logo" else ""
            output = quickshell.build_snapshot(data, selected, pending=_pending.copy(), logo_path=logo, logo_paths=logo_paths)
            if output["providers"] and any(selected.get(key) != output["selected"].get(key) for key in ("provider", "idx", "metric")):
                selected.update(output["selected"])
                state.save_selected(selected)
            serialized = json.dumps(output, ensure_ascii=False, allow_nan=False)
            if serialized != last_snapshot:
                print(serialized, flush=True)
                last_snapshot = serialized
        else:
            output = (render.build_loading_state(data, frame, selected, pending=_pending.copy())
                      if frame is not None else render.build_final_state(data, selected))
            print(json.dumps(output, ensure_ascii=False), flush=True)
            logos.write_tooltip(output.get("tooltip", ""))
            logos.signal_waybar()

    last_auto_update = time.time()
    last_update_check = 0
    last_config_mtime = None
    last_selected_mtime = 0
    last_refresh = paths.read_json(state.REFRESH_FILE)
    should_update = True
    selected = state.load_selected()

    if output_format == "quickshell":
        _pending = set(cfgmod.enabled_connection_order())
        emit(latest_data, selected)

    while True:
        try:
            now = time.time()
            if paths.IS_WINDOWS:
                refresh = paths.read_json(state.REFRESH_FILE)
                if refresh != last_refresh:
                    last_refresh = refresh
                    should_update = True
            
            if now - last_update_check >= 3600:
                fetch.check_for_updates()
                last_update_check = now
            
            config_mtime = tuple(os.path.getmtime(p) if os.path.exists(p) else 0
                                 for p in (cfgmod.CONFIG_FILE, cfgmod.accounts_file()))
            if config_mtime != last_config_mtime:
                last_config_mtime = config_mtime
                should_update = True

            selected_mtime = 0
            if os.path.exists(state.SELECTED_FILE):
                selected_mtime = os.path.getmtime(state.SELECTED_FILE)
            
            # Only re-parse selected.json when it changed — keeps the fast poll
            # cheap (the idle hot path is just two getmtime calls).
            if selected_mtime != last_selected_mtime:
                selected = state.load_selected()

            if should_update and not is_updating:
                should_update = False
                is_updating = True

                # Seed streaming state: start from the cached data (so each
                # provider animates its previous value) and mark every enabled
                # provider pending until its fresh result arrives.
                order = cfgmod.enabled_connection_order()
                _results_by_dir = _group_by_dir(latest_data)
                _pending = set(order)

                t = threading.Thread(target=update_task, args=(output_format,), daemon=True)
                t.start()

                frame = 0
                while is_updating:
                    # Selection must remain responsive while another provider
                    # is slow; both frontends use the same selection file.
                    selected = state.load_selected() or selected
                    merged = _ordered_merged(order)
                    emit(merged, selected, frame)
                    frame += 1
                    time.sleep(0.15)

                emit(latest_data, selected)
                last_auto_update = now
                last_selected_mtime = selected_mtime

            # Re-render on scroll (selected file changed, no re-fetch needed).
            # Polled at a short interval so the text/percentage follow the logo
            # (which the scroll command updates instantly) without a visible lag.
            elif selected_mtime != last_selected_mtime and not is_updating:
                last_selected_mtime = selected_mtime
                emit(latest_data, selected)
                if output_format == "waybar":
                    logos.update_current(selected)

            elif output_format == "quickshell":
                # Publish asynchronously downloaded logos without a new fetch.
                emit(latest_data, selected)

            # Short poll so the text reacts to a scroll/selection change almost
            # as fast as the logo (which updates instantly via its signal),
            # keeping the two in sync. The per-iteration work is tiny.
            time.sleep(0.15 if output_format == "quickshell" else 0.02)
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


def _terminate(signum, frame):
    raise KeyboardInterrupt


def run(output_format="waybar"):
    state.register_pid()
    previous = signal.signal(signal.SIGTERM, _terminate)
    previous_refresh = signal.signal(signal.SIGUSR1, handle_signal) if not paths.IS_WINDOWS else None
    try:
        _run(output_format)
    except KeyboardInterrupt:
        pass
    finally:
        state.unregister_pid()
        signal.signal(signal.SIGTERM, previous)
        if not paths.IS_WINDOWS:
            signal.signal(signal.SIGUSR1, previous_refresh)
