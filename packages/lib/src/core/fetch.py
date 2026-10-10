import importlib.util
import json
import os
import subprocess
import tempfile
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from . import __version__
from . import config as cfgmod
from . import paths
from .provider_http import request

CACHE_DIR = str(paths.CACHE_DIR / "providers") if paths.IS_WINDOWS else os.path.join(tempfile.gettempdir(), "ai-status-cache")
CACHE_TTL = 3600

def _cache_path(provider_dir):
    return os.path.join(CACHE_DIR, f"{os.path.basename(provider_dir)}.json")

def _save_cache(provider_dir, data):
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(provider_dir)
    try:
        paths.atomic_json(path, {"timestamp": time.time(), "data": data})
    except Exception:
        pass

def _load_cache(provider_dir):
    path = _cache_path(provider_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
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
        return "No compatible usage metrics returned; check authentication and CLI version."
    if isinstance(result, dict):
        for m in result.get("metrics") or []:
            if m.get("detail"):
                return m["detail"]
    return "No compatible usage metrics returned; check authentication and CLI version."

def query_command(query_script):
    if query_script.endswith(".py"):
        if getattr(sys, "frozen", False):
            # The GUI executable has no console streams. Its sibling CLI does.
            executable = os.path.join(os.path.dirname(sys.executable), "ai-status-cli.exe")
            return [executable, "--query", os.path.basename(os.path.dirname(query_script))]
        return [sys.executable, query_script]
    return ["bash", query_script]


def _cached_or_error(provider_dir, message):
    cached = _load_cache(provider_dir)
    if cached:
        for item in cached if isinstance(cached, list) else [cached]:
            item["_cached"] = True
            item["_error"] = message
        return cached
    return {"error": message}


def run_query(name):
    """Internal collector entry point used by the frozen CLI subprocess."""
    if name not in cfgmod.available_providers():
        raise ValueError("Unknown provider")
    script = os.path.join(cfgmod.providers_dir(), name, "query.py")
    spec = importlib.util.spec_from_file_location(f"query_{name}", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()


def run_provider(provider_dir):
    query_script = os.path.join(provider_dir, "query.py")
    if not os.path.exists(query_script):
        query_script = os.path.join(provider_dir, "query.sh")
    parse_script = os.path.join(provider_dir, "parse.py")

    if not os.path.exists(query_script):
        return None

    try:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.dirname(cfgmod.providers_dir()) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if paths.IS_WINDOWS else {}
        res = subprocess.run(query_command(query_script), capture_output=True, text=True,
                             encoding="utf-8", errors="replace", env=env, timeout=40, **options)
        if res.returncode != 0:
            return _cached_or_error(provider_dir, f"Query failed for {os.path.basename(provider_dir)}; check authentication and CLI compatibility.")

        raw_output = res.stdout.strip()
        if not raw_output:
            return _cached_or_error(provider_dir, "No usage returned; check authentication.")

        if raw_output.startswith("{"):
            try:
                message = json.loads(raw_output).get("_ai_status_error")
            except (ValueError, AttributeError):
                message = None
            if message:
                return _cached_or_error(provider_dir, message)

        if os.path.exists(parse_script):
            spec = importlib.util.spec_from_file_location("parse", parse_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.parse(raw_output)
        else:
            result = json.loads(raw_output)

        if _is_error_result(result):
            return _cached_or_error(provider_dir, _extract_error_detail(result))

        _save_cache(provider_dir, result)
        return result

    except subprocess.TimeoutExpired:
        return _cached_or_error(provider_dir, "Usage query timed out.")
    except Exception:
        return _cached_or_error(provider_dir, "Unable to read usage; check credentials and provider response format.")

_latest_version = None

def check_for_updates():
    global _latest_version
    try:
        data = json.loads(request(
            "https://api.github.com/repos/gelzinn/ai-status/releases/latest",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ai-status",
            },
            timeout=5,
        ))
        tag = data.get("tag_name", "")
        _latest_version = tag.lstrip("v")
    except Exception:
        pass

def get_version_info():
    return {
        "current": __version__,
        "latest": _latest_version,
        "has_update": _latest_version is not None and _latest_version != __version__,
    }

def fetch_all_data(on_result=None, on_error=None, include_errors=False):
    repo_dir = cfgmod.providers_dir()
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

    dir_to_results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(ordered_dirs))) as executor:
        future_to_dir = {executor.submit(run_provider, d): d for d in ordered_dirs}
        for future in as_completed(future_to_dir):
            d = future_to_dir[future]
            dir_name = os.path.basename(d)
            providers = None
            try:
                data = future.result()
                if include_errors and (not data or isinstance(data, dict) and "error" in data):
                    data = {"provider": dir_name, "metrics": [], "_error": (data or {}).get("error", "No usage data available")}
                if data and "error" not in data:
                    providers = data if isinstance(data, list) else [data]
                    for idx, p in enumerate(providers):
                        if isinstance(p, dict):
                            p["_dir"] = dir_name
                            p["_idx"] = idx
                    dir_to_results[d] = providers
                elif on_error:
                    on_error(dir_name, (data or {}).get("error", "No usage available."))
            except Exception:
                providers = None
                if on_error:
                    on_error(dir_name, "Unable to read usage.")
            # Report each provider the moment it finishes so callers can render
            # incrementally instead of waiting for the slowest one.
            if on_result:
                on_result(dir_name, providers)

    results = []
    for d in ordered_dirs:
        if d in dir_to_results:
            results.extend(dir_to_results[d])
    return results
