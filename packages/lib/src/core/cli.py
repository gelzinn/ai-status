import os
import sys
import time
import subprocess
import argparse
import json
from . import daemon
from . import state
from . import logos
from . import render
from . import config as cfgmod
from . import quickshell, paths, fetch

TERMINALS = ["foot", "alacritty", "kitty", "ghostty", "wezterm", "xterm"]


def _provider_metric_keys(cache, dir_name, idx):
    """Ordered list of a provider's metric keys (same order the tooltip shows).
    Keys, not types, so metrics that share a type (e.g. Claude's general vs
    Fable weekly) are individually selectable."""
    for p in cache:
        if p.get("_dir") == dir_name and p.get("_idx") == idx:
            metrics = sorted(
                p.get("metrics", []),
                key=lambda m: render.TYPE_ORDER.get(m.get("type", "generic"), 4),
            )
            return [render.metric_key(m) for m in metrics]
    return []


def _first_metric_for(cache, dir_name, idx):
    keys = _provider_metric_keys(cache, dir_name, idx)
    return keys[0] if keys else "rolling"

def _scroll(direction, frontend="waybar"):
    providers = cfgmod.enabled_order()
    if not providers:
        return

    cache = state.load_cache()
    if frontend in ("quickshell", "macos", "swiftbar"):
        cache = [dict(p, metrics=quickshell.usable_metrics(p)) for p in cache if quickshell.usable_metrics(p)]
    items = []
    seen = set()
    for p in cache:
        if p.get("metrics") and p.get("_dir") in providers:
            key = (p.get("_dir"), p.get("_idx", 0))
            if key not in seen:
                seen.add(key)
                items.append(key)

    if not items:
        if frontend in ("quickshell", "macos", "swiftbar"):
            return
        items = [(p, 0) for p in providers]

    selected = state.load_selected() or {}
    current_dir = selected.get("provider")
    current_idx = selected.get("idx", 0)

    try:
        idx = items.index((current_dir, current_idx))
    except (ValueError, IndexError):
        idx = -1 if direction > 0 else 0

    new_dir, new_idx = items[(idx + direction) % len(items)]
    new_metric = _first_metric_for(cache, new_dir, new_idx)
    
    selected["provider"] = new_dir
    selected["idx"] = new_idx
    selected["metric"] = new_metric

    state.save_selected(selected)
    if frontend == "waybar":
        logos.update_current(selected)

def scroll_up(frontend="waybar"):
    _scroll(-1, frontend)

def scroll_down(frontend="waybar"):
    _scroll(1, frontend)

def cycle_metric(frontend="waybar"):
    selected = state.load_selected() or {}
    provider = selected.get("provider")
    idx = selected.get("idx", 0)
    current = selected.get("metric", "rolling")
    
    cache = state.load_cache()
    if frontend in ("quickshell", "macos", "swiftbar"):
        cache = [dict(p, metrics=quickshell.usable_metrics(p)) for p in cache if quickshell.usable_metrics(p)]
    keys = _provider_metric_keys(cache, provider, idx)

    if len(keys) <= 1:
        return

    try:
        pos = keys.index(current)
    except ValueError:
        pos = -1
    
    new_metric = keys[(pos + 1) % len(keys)]
    
    selected["provider"] = provider
    selected["idx"] = idx
    selected["metric"] = new_metric

    state.save_selected(selected)


# ── macOS / SwiftBar ──────────────────────────────────────────────────────
# macOS has no Waybar daemon streaming JSON. SwiftBar runs a plugin script on
# an interval (or as a long-lived streamable process) and renders its stdout.
# The plugin reads the shared cache and renders; a refresh is a detached child
# so the short-lived plugin invocation never blocks on the network.

SWIFTBAR_STALE_SECS = 300  # background-refresh cadence, matching the daemon


def _cache_age():
    try:
        return time.time() - os.path.getmtime(state.CACHE_FILE)
    except OSError:
        return None


def _refresh_in_flight():
    """True while *any* refresh holds the query lock — our own background thread,
    the ``Refresh`` menu action, or the periodic plugin's spawned child. Lets the
    stream animate the spark for a manual refresh too, not just its own."""
    try:
        return time.time() - os.path.getmtime(state.LOCK_FILE) < 90
    except OSError:
        return False


def _swiftbar_refresh():
    """Fetch every enabled provider and save the shared cache (blocking).

    Used both by the background refresh and by the "Refresh" menu action. The
    query lock keeps two refreshes from running at once — if one already holds
    it, this call is a no-op and the running one updates the cache."""
    from . import fetch
    if sys.platform == "darwin":
        from .macos import configure_environment
        configure_environment()

    if not state.acquire_lock():
        return
    try:
        data = fetch.fetch_all_data(include_errors=True)
        if data:
            state.save_cache(data)
    finally:
        state.release_lock()


def _spawn_background_refresh():
    """Detach a child running ``swiftbar-refresh`` so the cache refreshes out of
    band. A thread would die with the plugin process, so this must be its own
    session. Skips spawning when a refresh is already in flight."""
    if not state.acquire_lock():
        return
    state.release_lock()  # only probed for one in flight; the child re-acquires
    try:
        subprocess.Popen(
            [sys.executable, os.path.realpath(sys.argv[0]), "swiftbar-refresh"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def _swiftbar_select(args):
    """Set the active provider/metric from a menu click (replaces Waybar scroll).

    ``args`` = [dir_name, idx, metric_key?]. A missing metric falls back to the
    provider's first metric."""
    # SwiftBar may or may not strip surrounding quotes from param values; strip
    # defensively so ``param4="rolling"`` never arrives as the literal `"rolling"`
    # (which would fail every comparison and make clicks a silent no-op).
    args = [a[1:-1] if len(a) >= 2 and a[0] == '"' and a[-1] == '"' else a for a in args]
    if not args:
        return
    dir_name = args[0]
    try:
        idx = int(args[1]) if len(args) > 1 else 0
    except ValueError:
        idx = 0
    metric = args[2] if len(args) > 2 else None
    quickshell.select_metric({"provider": dir_name, "idx": idx,
                              "metric": metric or _first_metric_for(state.load_cache(), dir_name, idx)})


def swiftbar_render():
    """Print the SwiftBar menu from the cache, kicking a background refresh when
    the cache is missing or stale."""
    from . import swiftbar as sb

    age = _cache_age()
    if age is None or age >= SWIFTBAR_STALE_SECS:
        _spawn_background_refresh()
    print(sb.render_from_state())


def _swiftbar_sig():
    """Cheap change signature (cache + selection mtimes) so the idle stream only
    re-emits when something actually changed."""
    def mt(path):
        try:
            return os.path.getmtime(path)
        except OSError:
            return 0
    return (mt(state.CACHE_FILE), mt(state.SELECTED_FILE), mt(cfgmod.CONFIG_FILE))


def swiftbar_stream():
    """Long-lived SwiftBar *streamable* plugin.

    Renders from the shared cache (the Tier-1 model) and animates the Claude
    spark in the menu bar while a refresh is in flight — the menu-bar analogue
    of the shimmer the Linux tooltip shows. SwiftBar keeps this process alive,
    so the refresh runs in a background thread and the loop streams one full
    menu per frame, each terminated by SwiftBar's ``~~~`` separator.
    """
    import signal
    import threading
    from . import swiftbar as sb

    state.register_pid()  # lets `ai-status refresh` (SIGUSR1) poke us
    refreshing = threading.Event()

    def do_refresh():
        refreshing.set()
        try:
            _swiftbar_refresh()
        finally:
            refreshing.clear()

    def kick(*_):
        if not refreshing.is_set():
            threading.Thread(target=do_refresh, daemon=True).start()

    try:
        signal.signal(signal.SIGUSR1, kick)
    except (ValueError, OSError):
        pass

    FRAME_DELAY = 0.12   # spark animation cadence
    IDLE_POLL = 0.4      # responsiveness to menu-click selection changes
    HEARTBEAT = 30.0     # re-emit at least this often when idle
    last_auto = 0.0
    last_sig = None
    last_emit = 0.0
    frame_idx = 0

    age = _cache_age()
    if age is None or age >= SWIFTBAR_STALE_SECS:
        kick()

    while True:
        try:
            now = time.time()
            age = _cache_age()
            if (not refreshing.is_set()
                    and (age is None or age >= SWIFTBAR_STALE_SECS)
                    and now - last_auto >= SWIFTBAR_STALE_SECS):
                last_auto = now
                kick()

            cache = state.load_cache()
            selected = state.load_selected()

            if refreshing.is_set() or _refresh_in_flight():
                spinner = sb.SPINNERS[frame_idx % len(sb.SPINNERS)]
                menu = sb.render_menu(
                    cache, selected,
                    spinner=spinner,
                    title_image=sb.spark_frame(frame_idx),
                )
                sys.stdout.write(menu + "\n~~~\n")
                sys.stdout.flush()
                frame_idx += 1
                last_sig = None  # force one fresh emit when the animation ends
                time.sleep(FRAME_DELAY)
            else:
                frame_idx = 0
                sig = _swiftbar_sig()
                if sig != last_sig or now - last_emit >= HEARTBEAT:
                    sys.stdout.write(sb.render_menu(cache, selected) + "\n~~~\n")
                    sys.stdout.flush()
                    last_sig = sig
                    last_emit = now
                time.sleep(IDLE_POLL)
        except (BrokenPipeError, KeyboardInterrupt):
            break
        except Exception:
            time.sleep(1)


def print_logo():
    """Output for the waybar image module: line 1 is the logo PNG path, line 2
    is the tooltip (the same rich breakdown as the text module).

    Newlines in the tooltip are encoded as U+2028 (LINE SEPARATOR) so waybar
    keeps it as a single output line — the image module only reads one line of
    tooltip — while Pango still renders the breaks. This is what lets hovering
    the logo show the full tooltip, not just the icon.
    """
    selected = state.load_selected() or {}
    if state.get_icon_mode(selected) != "logo":
        print("")
        return
    # current.png is kept up to date by the daemon (startup + selection change)
    # and the scroll command; only seed it here if it's missing so this hot path
    # (called once per loading frame) stays a couple of file reads.
    if not os.path.exists(logos.CURRENT_PNG):
        logos.update_current(selected, notify=False)
    path = logos.CURRENT_PNG if os.path.exists(logos.CURRENT_PNG) else ""

    # Prefer the live tooltip the daemon mirrors (so the logo shows the same
    # loading animation as the text); fall back to a fresh render if absent.
    tooltip = ""
    try:
        if os.path.exists(logos.TOOLTIP_FILE):
            with open(logos.TOOLTIP_FILE, encoding="utf-8") as f:
                tooltip = f.read()
        else:
            tooltip = render.build_final_state(state.load_cache(), selected).get("tooltip", "")
        tooltip = tooltip.replace("\n", " ")
    except Exception:
        tooltip = ""

    sys.stdout.write(f"{path}\n{tooltip}")


def revert_waybar():
    """Restore the Waybar config we backed up before configuring it — a clean
    undo for an automatic setup, in case anything looks off."""
    import shutil
    cfg = os.path.expanduser("~/.config/waybar/config.jsonc")
    bak = cfg + ".ai-status.bak"
    if not os.path.exists(bak):
        print("No AI Status backup found — nothing to revert.")
        print("(A backup is only made when you let the installer configure Waybar for you;")
        print(" if you added the modules by hand, just remove them yourself.)")
        return
    try:
        if os.path.exists(cfg):
            shutil.copy2(cfg, cfg + ".pre-revert")  # keep the revert itself undoable
        shutil.copy2(bak, cfg)
    except Exception as e:
        print(f"Could not restore the backup: {e}")
        sys.exit(1)
    print(f"Restored your original Waybar config from:\n  {bak}")
    try:
        subprocess.run(["pkill", "-SIGUSR2", "waybar"], capture_output=True, timeout=3)
        print("Reloaded Waybar — the ai-status modules were removed.")
    except Exception:
        print("Restart Waybar to apply the change.")


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "--query":
        if len(sys.argv) != 3:
            raise SystemExit("Usage: ai-status --query PROVIDER")
        fetch.run_query(sys.argv[2])
    elif command == "doctor":
        info = {"version": fetch.get_version_info()["current"],
                "providers": cfgmod.available_providers(), "config": str(paths.CONFIG_DIR),
                "cache": str(paths.CACHE_DIR), "desktop": False, "conpty": False}
        try:
            from . import tray
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
            info["desktop"] = not tray.status_icon().isNull()
            if paths.IS_WINDOWS:
                from .windows_console import available
                info["conpty"] = available()
            if "--smoke" in sys.argv:
                info.update(tray.smoke_test())
        except ImportError:
            pass
        if "--http-smoke" in sys.argv:
            from .provider_http import request
            response = json.loads(request("https://api.github.com/", timeout=10))
            info["native_https"] = paths.IS_WINDOWS and "current_user_url" in response
        print(json.dumps(info, ensure_ascii=False))
    elif command == "status":
        errors = {}
        data = fetch.fetch_all_data(on_error=lambda name, message: errors.update({name: message}))
        state.save_cache(data)
        print(json.dumps({"providers": data, "errors": errors}, ensure_ascii=False))
    elif command in ("swiftbar", "swiftbar-stream", "swiftbar-refresh", "swiftbar-select"):
        actions = {"swiftbar": swiftbar_render, "swiftbar-stream": swiftbar_stream,
                   "swiftbar-refresh": _swiftbar_refresh}
        if command == "swiftbar-select":
            try:
                _swiftbar_select(sys.argv[2:])
            except (ValueError, OSError) as error:
                print(str(error), file=sys.stderr)
                return 1
        else:
            actions[command]()
    elif command == "macos" or (sys.platform == "darwin" and command in ("", "config") and "--frontend" not in sys.argv):
        from . import macos
        macos.launch(configure=command == "config" or "--settings" in sys.argv)
    elif command == "tray" or (paths.IS_WINDOWS and command in ("", "config")):
        from . import tray
        tray.run(configure=command == "config")

    else:
        return _frontend_main()


def _frontend_main():
    parser = argparse.ArgumentParser(prog="ai-status")
    parser.add_argument("command", choices=["daemon", "refresh", "config", "save-settings", "select-metric", "scroll-up", "scroll-down", "cycle-metric", "logo", "revert"])
    parser.add_argument("--format", choices=["waybar", "quickshell", "macos"], default="waybar")
    parser.add_argument("--frontend", choices=["waybar", "quickshell", "macos", "swiftbar"], default="waybar")
    parser.add_argument("--settings-json")
    parser.add_argument("--selection-json")
    args = parser.parse_args()
    if args.format != "waybar" and args.command != "daemon":
        parser.error("--format is only supported by daemon")
    if args.settings_json is not None and args.command != "save-settings":
        parser.error("--settings-json is only supported by save-settings")
    if args.selection_json is not None and args.command != "select-metric":
        parser.error("--selection-json is only supported by select-metric")
    if args.command == "select-metric":
        if args.frontend not in ("quickshell", "macos") or args.selection_json is None:
            parser.error("select-metric requires --frontend quickshell|macos and --selection-json")
        try:
            quickshell.select_metric(json.loads(args.selection_json))
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "save-settings":
        if args.frontend not in ("quickshell", "macos") or args.settings_json is None:
            parser.error("save-settings requires --frontend quickshell|macos and --settings-json")
        try:
            quickshell.save_settings(json.loads(args.settings_json))
        except (ValueError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
    elif args.command == "refresh":
        state.trigger_refresh()
    elif args.command == "daemon":
        if args.format == "waybar":
            paths.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            sys.stderr = open(paths.LOG_FILE, 'w', encoding='utf-8')
        daemon.run(output_format=args.format)
    elif args.command == "config":
        from . import tui
        if not sys.stdout.isatty():
            for term in TERMINALS:
                if subprocess.run(["which", term], capture_output=True).returncode == 0:
                    subprocess.Popen([term, "-e", sys.executable, os.path.realpath(sys.argv[0]), "config"])
                    break
            return
        tui.run()
    elif args.command == "scroll-up":
        scroll_up(args.frontend)
    elif args.command == "scroll-down":
        scroll_down(args.frontend)
    elif args.command == "cycle-metric":
        cycle_metric(args.frontend)
    elif args.command == "logo":
        print_logo()
    elif args.command == "revert":
        revert_waybar()
