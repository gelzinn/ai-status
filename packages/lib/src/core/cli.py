import os
import sys
import subprocess
from . import daemon
from . import state
from . import logos
from . import render
from . import config as cfgmod
from . import paths
from . import fetch

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

def _scroll(direction):
    providers = cfgmod.enabled_order()
    if not providers:
        return

    cache = state.load_cache()
    items = []
    seen = set()
    for p in cache:
        if p.get("metrics"):
            key = (p.get("_dir"), p.get("_idx", 0))
            if key not in seen:
                seen.add(key)
                items.append(key)

    if not items:
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
    logos.update_current(selected)

def scroll_up():
    _scroll(-1)

def scroll_down():
    _scroll(1)

def cycle_metric():
    selected = state.load_selected() or {}
    provider = selected.get("provider")
    idx = selected.get("idx", 0)
    current = selected.get("metric", "rolling")
    
    keys = _provider_metric_keys(state.load_cache(), provider, idx)

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
        import json
        info = {"version": fetch.get_version_info()["current"],
                "providers": cfgmod.available_providers(), "config": str(paths.CONFIG_DIR),
                "cache": str(paths.CACHE_DIR), "desktop": False, "conpty": False}
        try:
            from . import tray
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication([])
            info["desktop"] = not tray.status_icon().isNull()
            if paths.IS_WINDOWS:
                from winpty import Backend, PtyProcess
                info["conpty"] = hasattr(Backend, "ConPTY") and callable(PtyProcess.spawn)
        except ImportError:
            pass
        print(json.dumps(info, ensure_ascii=False))
    elif command == "status":
        import json
        errors = {}
        data = fetch.fetch_all_data(on_error=lambda name, message: errors.update({name: message}))
        state.save_cache(data)
        print(json.dumps({"providers": data, "errors": errors}, ensure_ascii=False))
    elif command == "tray" or (paths.IS_WINDOWS and command in ("", "config")):
        from . import tray
        tray.run(configure=command == "config")
    elif command == "refresh":
        state.trigger_refresh()
    elif len(sys.argv) > 1 and sys.argv[1] == "daemon":
        paths.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        sys.stderr = open(paths.LOG_FILE, 'w', encoding="utf-8")
        daemon.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "config":
        from . import tui
        if not sys.stdout.isatty():
            for term in TERMINALS:
                if subprocess.run(["which", term], capture_output=True).returncode == 0:
                    subprocess.Popen([term, "-e", sys.argv[0], "config"])
                    break
            return
        tui.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "scroll-up":
        scroll_up()
    elif len(sys.argv) > 1 and sys.argv[1] == "scroll-down":
        scroll_down()
    elif len(sys.argv) > 1 and sys.argv[1] == "cycle-metric":
        cycle_metric()
    elif len(sys.argv) > 1 and sys.argv[1] == "logo":
        print_logo()
    elif len(sys.argv) > 1 and sys.argv[1] == "revert":
        revert_waybar()
    else:
        print("Usage: ai-status [tray|status|doctor|daemon|refresh|config|scroll-up|scroll-down|cycle-metric|logo|revert]")
        sys.exit(1)
