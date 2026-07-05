import os
import sys
import shutil
import subprocess

from . import daemon
from . import state
from . import tui
from . import config as cfgmod
from . import types as metric_types

TERMINALS = ["foot", "alacritty", "kitty", "ghostty", "wezterm", "xterm", "Terminal", "iTerm2", "warp"]

def _first_metric_for(cache, dir_name, idx):
    for p in cache:
        if p.get("_dir") == dir_name and p.get("_idx") == idx:
            available = {m.get("type") for m in p.get("metrics", []) if m.get("type") in metric_types.METRIC_CYCLE}
            for t in metric_types.METRIC_CYCLE:
                if t in available:
                    return t
            if p.get("metrics"):
                return p["metrics"][0].get("type", "rolling")
            return "rolling"
    return "rolling"

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
    state.save_selected({"provider": new_dir, "idx": new_idx, "metric": new_metric})

def scroll_up():
    _scroll(-1)

def scroll_down():
    _scroll(1)

def cycle_metric():
    selected = state.load_selected() or {}
    provider = selected.get("provider")
    idx = selected.get("idx", 0)
    current = selected.get("metric", "rolling")
    
    cache = state.load_cache()
    available = set()
    for p in cache:
        if p.get("_dir") == provider and p.get("_idx") == idx:
            for m in p.get("metrics", []):
                t = m.get("type")
                if t in metric_types.METRIC_CYCLE:
                    available.add(t)
            break

    cycle = sorted(available, key=lambda t: metric_types.METRIC_CYCLE.index(t)) if available else metric_types.METRIC_CYCLE
    if not cycle:
        cycle = metric_types.METRIC_CYCLE

    if len(available) <= 1:
        return

    try:
        pos = cycle.index(current)
    except ValueError:
        pos = -1
    
    new_metric = cycle[(pos + 1) % len(cycle)]
    state.save_selected({"provider": provider, "idx": idx, "metric": new_metric})

def _swiftbar_output():
    from .platform.macos import swiftbar
    sys.stdout.write(swiftbar.render(state.load_cache(), state.load_selected()))
    sys.stdout.flush()

SWIFTBAR_ACTIONS = {
    "swiftbar": lambda: None,
    "swiftbar-refresh": state.trigger_refresh,
    "swiftbar-scroll-up": scroll_up,
    "swiftbar-scroll-down": scroll_down,
    "swiftbar-cycle-metric": cycle_metric,
}

def run_config():
    if not sys.stdout.isatty():
        for term in TERMINALS:
            if shutil.which(term):
                subprocess.Popen([term, "-e", sys.argv[0], "config"])
                return
    tui.run()

def main():
    if len(sys.argv) <= 1:
        print("Usage: ai-status [daemon|refresh|config|scroll-up|scroll-down|cycle-metric|swiftbar|swiftbar-refresh|swiftbar-scroll-up|swiftbar-scroll-down|swiftbar-cycle-metric]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "refresh":
        state.trigger_refresh()
    elif cmd == "daemon":
        os.makedirs(state._cache_dir, exist_ok=True)
        sys.stderr = open(os.path.join(state._cache_dir, "daemon.log"), 'w')
        daemon.run()
    elif cmd == "config":
        run_config()
    elif cmd == "scroll-up":
        scroll_up()
    elif cmd == "scroll-down":
        scroll_down()
    elif cmd == "cycle-metric":
        cycle_metric()
    elif cmd in SWIFTBAR_ACTIONS:
        SWIFTBAR_ACTIONS[cmd]()
        _swiftbar_output()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
