import os
import subprocess
import json
import importlib.util
import urllib.request
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import __version__
from . import config as cfgmod

def run_provider(provider_dir):
    query_script = os.path.join(provider_dir, "query.sh")
    parse_script = os.path.join(provider_dir, "parse.py")
    
    if not os.path.exists(query_script):
        return None
        
    try:
        # 1. Query: Puxa os dados (Bash faz o curl e cospe na tela)
        res = subprocess.run([query_script], capture_output=True, text=True, timeout=20)
        if res.returncode != 0:
            return {"error": f"Query failed for {os.path.basename(provider_dir)}"}
            
        raw_output = res.stdout.strip()
        if not raw_output:
            return None
            
        # 2. Parse: Se o parse.py existir, formata o array em Python
        if os.path.exists(parse_script):
            spec = importlib.util.spec_from_file_location("parse", parse_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module.parse(raw_output)
        else:
            # Fallback temporário: tenta ler como JSON direto (scripts antigos)
            return json.loads(raw_output)
            
    except subprocess.TimeoutExpired:
        return {"error": "Timeout"}
    except Exception as e:
        return {"error": str(e)}

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
