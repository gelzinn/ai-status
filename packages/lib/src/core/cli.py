import os
import sys
import subprocess
from . import daemon
from . import state
from . import tui
from . import config as cfgmod

TERMINALS = ["foot", "alacritty", "kitty", "ghostty", "wezterm", "xterm"]

METRIC_CYCLE = ["rolling", "weekly", "monthly"]

def _first_metric_for(cache, dir_name, idx):
    for p in cache:
        if p.get("_dir") == dir_name and p.get("_idx") == idx:
            available = {m.get("type") for m in p.get("metrics", []) if m.get("type") in METRIC_CYCLE}
            for t in METRIC_CYCLE:
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
    
    selected["provider"] = new_dir
    selected["idx"] = new_idx
    selected["metric"] = new_metric
    
    state.save_selected(selected)

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
                if t in METRIC_CYCLE:
                    available.add(t)
            break

    cycle = sorted(available, key=lambda t: METRIC_CYCLE.index(t)) if available else METRIC_CYCLE
    if not cycle:
        cycle = METRIC_CYCLE

    if len(available) <= 1:
        return

    try:
        pos = cycle.index(current)
    except ValueError:
        pos = -1
    
    new_metric = cycle[(pos + 1) % len(cycle)]
    
    selected["provider"] = provider
    selected["idx"] = idx
    selected["metric"] = new_metric

    state.save_selected(selected)

def print_logo():
    selected = state.load_selected() or {}
    provider = selected.get("provider", "antigravity")
    
    shared_json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "shared", "providers", "providers.json")
    try:
        import json, urllib.request
        with open(shared_json_path, 'r') as f:
            providers = json.load(f)
        
        logo_url = providers.get(provider, {}).get("logo")
        if not logo_url:
            logo_url = providers.get("antigravity", {}).get("logo")
            
        if logo_url:
            cache_dir = os.path.expanduser("~/.cache/ai-status/logos")
            os.makedirs(cache_dir, exist_ok=True)
            # Basic extension extraction, defaulting to svg for google favicons etc
            ext = logo_url.split(".")[-1]
            if len(ext) > 4 or "?" in ext: ext = "svg"
            local_path = os.path.join(cache_dir, f"{provider}.{ext}")
            
            if not os.path.exists(local_path):
                req = urllib.request.Request(logo_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response, open(local_path, 'wb') as out_file:
                    out_file.write(response.read())
                    
            print(local_path)
    except Exception as e:
        print("")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "refresh":
        state.trigger_refresh()
    elif len(sys.argv) > 1 and sys.argv[1] == "daemon":
        sys.stderr = open('/tmp/ai-status-error.log', 'w')
        daemon.run()
    elif len(sys.argv) > 1 and sys.argv[1] == "config":
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
    else:
        print("Usage: ai-status [daemon|refresh|config|scroll-up|scroll-down|cycle-metric|logo]")
        sys.exit(1)
