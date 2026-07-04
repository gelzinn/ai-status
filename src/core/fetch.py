import os
import subprocess
import json
import importlib.util
import urllib.request
import re
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import __version__
from . import config as cfgmod

CACHE_DIR = os.path.join(tempfile.gettempdir(), "waybar-ai-status-cache")
CACHE_TTL = 3600


def _cache_path(provider_dir):
    return os.path.join(CACHE_DIR, f"{os.path.basename(provider_dir)}.json")


def _save_cache(provider_dir, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(provider_dir)
    try:
        with open(path, "w") as f:
            json.dump({"timestamp": time.time(), "data": data}, f)
    except Exception:
        pass


def _load_cache(provider_dir):
    path = _cache_path(provider_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            cache = json.load(f)
        if time.time() - cache.get("timestamp", 0) < CACHE_TTL:
            return cache["data"]
    except Exception:
        pass
    return None


def _is_error_result(result):
    if result is None:
        return True
    if isinstance(result, list):
        return all(_is_error_result(item) for item in result)
    if isinstance(result, dict):
        if "error" in result:
            return True
        metrics = result.get("metrics", [])
        if not metrics:
            return True
        if all(m.get("percentage", 0) == 0 for m in metrics):
            error_kw = ["rate limit", "unreachable", "failed", "auth"]
            for m in metrics:
                detail = (m.get("detail") or "").lower()
                if any(kw in detail for kw in error_kw):
                    return True
    return False


def _extract_error_detail(result):
    if isinstance(result, list):
        for item in result:
            d = _extract_error_detail(item)
            if d:
                return d
        return "Unknown error"
    if isinstance(result, dict):
        for m in (result.get("metrics") or []):
            if m.get("detail"):
                return m["detail"]
    return "Unknown error"


def run_provider(provider_dir):
    query_script = os.path.join(provider_dir, "query.sh")
    parse_script = os.path.join(provider_dir, "parse.py")
    
    if not os.path.exists(query_script):
        return None
        
    try:
        res = subprocess.run([query_script], capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return _load_cache(provider_dir) or {"error": f"Query failed for {os.path.basename(provider_dir)}"}
            
        raw_output = res.stdout.strip()
        if not raw_output:
            return _load_cache(provider_dir) or None
            
        if os.path.exists(parse_script):
            spec = importlib.util.spec_from_file_location("parse", parse_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.parse(raw_output)
        else:
            result = json.loads(raw_output)
        
        if _is_error_result(result):
            cached = _load_cache(provider_dir)
            if cached:
                detail = _extract_error_detail(result)
                if isinstance(cached, list):
                    for item in cached:
                        if isinstance(item, dict):
                            item["_cached"] = True
                            item["_error"] = detail
                else:
                    cached = dict(cached)
                    cached["_cached"] = True
                    cached["_error"] = detail
                return cached
            return result
        
        _save_cache(provider_dir, result)
        return result
        
    except subprocess.TimeoutExpired:
        return _load_cache(provider_dir) or {"error": "Timeout"}
    except Exception as e:
        return _load_cache(provider_dir) or {"error": str(e)}
_latest_version = None

def check_for_updates():
    global _latest_version
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/gelzinn/omarchy-ai-status/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "omarchy-ai-status"}
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            tag = data.get("tag_name", "")
            _latest_version = tag.lstrip("v")
    except Exception:
        pass

def get_version_info():
    return {
        "current": __version__,
        "latest": _latest_version,
        "has_update": _latest_version is not None and _latest_version != __version__
    }

def fetch_all_data():
    repo_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "providers")
    script_dir = repo_dir
    
    if not os.path.exists(script_dir):
        return []
        
    enabled_order = cfgmod.enabled_order()
    enabled_set = set(enabled_order)
    
    provider_dirs = []
    for d in os.listdir(script_dir):
        if not os.path.isdir(os.path.join(script_dir, d)):
            continue
        if d in ("__pycache__", "gemini-cli"):
            continue
        if d not in enabled_set:
            continue
        provider_dirs.append((d, os.path.join(script_dir, d)))
    
    name_to_dir = {name: path for name, path in provider_dirs}
    ordered_dirs = []
    for name in enabled_order:
        if name in name_to_dir:
            ordered_dirs.append(name_to_dir[name])
    
    with ThreadPoolExecutor(max_workers=max(1, len(ordered_dirs))) as executor:
        future_to_dir = {executor.submit(run_provider, d): d for d in ordered_dirs}
        
    dir_to_results = {}
    for future in as_completed(future_to_dir):
        d = future_to_dir[future]
        try:
            data = future.result(timeout=18)
            if data and "error" not in data:
                providers = data if isinstance(data, list) else [data]
                dir_to_results[d] = providers
        except Exception:
            pass
    
    results = []
    for d in ordered_dirs:
        if d in dir_to_results:
            dir_name = os.path.basename(d)
            for idx, p in enumerate(dir_to_results[d]):
                if isinstance(p, dict):
                    p["_dir"] = dir_name
                    p["_idx"] = idx
            results.extend(dir_to_results[d])
    return results
