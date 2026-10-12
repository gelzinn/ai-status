import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlsplit

from . import __version__
from . import config as cfgmod
from . import paths
from . import accounts
from . import usage_credits
from .provider_http import request

CACHE_DIR = str(paths.CACHE_DIR / "providers")
CACHE_TTL = 3600
MIN_REFRESH_SECONDS = 60
MIN_SERVICE_INTERVAL = 1
_SERVICE_LOCKS = {}
_SERVICE_LOCKS_GUARD = threading.Lock()
_SERVICE_LAST_START = {}


def _service_key(provider):
    # Several adapters share a vendor's rate-limit pool even when their URL
    # paths differ. Keep requests for those adapters sequential.
    return {"claude": "anthropic", "anthropic-api": "anthropic",
               "codex": "openai", "openai-api": "openai",
               "cursor": "cursor", "grok-bot": "cursor",
               "grok": "xai", "supergrok": "xai"}.get(provider, provider)


def _service_lock(provider):
    service = _service_key(provider)
    with _SERVICE_LOCKS_GUARD:
        return _SERVICE_LOCKS.setdefault(service, threading.Lock())


def _pace_service(provider):
    service = _service_key(provider)
    wait = MIN_SERVICE_INTERVAL - (time.monotonic() - _SERVICE_LAST_START.get(service, float("-inf")))
    if wait > 0:
        time.sleep(wait)
    _SERVICE_LAST_START[service] = time.monotonic()


def _cooldown_path(fingerprint):
    return os.path.join(CACHE_DIR, f"{fingerprint}.cooldown.json")


def _cooldown_remaining(connection, fingerprint):
    try:
        with open(_cooldown_path(fingerprint), encoding="utf-8") as stream:
            data = json.load(stream)
        if data.get("fingerprint") != fingerprint or data.get("connection_id") != connection["connection_id"]:
            return 0
        end = float(data.get("next_allowed_at", 0))
        return max(0, math.ceil(end - time.time())) if math.isfinite(end) else 0
    except (OSError, ValueError, TypeError, AttributeError):
        return 0


def _save_cooldown(connection, fingerprint, retry_after):
    try:
        delay = float(retry_after)
        if not math.isfinite(delay):
            delay = 300
    except (ValueError, TypeError, OverflowError):
        delay = 300
    delay = min(86400, max(1, delay))
    try:
        os.makedirs(CACHE_DIR, exist_ok=True, mode=0o700)
        paths.atomic_json(_cooldown_path(fingerprint), {
            "connection_id": connection["connection_id"], "fingerprint": fingerprint,
            "next_allowed_at": time.time() + delay,
        })
    except OSError:
        pass
    return math.ceil(delay)


def _rate_limit_message(seconds):
    return f"Rate limited; next attempt in {seconds} seconds."

def _default_connection(provider_dir):
    name = os.path.basename(provider_dir)
    return {"provider": name, "connection_id": name, "account_id": None, "env": {}, "options": {}}


def _cache_context(provider_dir, connection=None, fingerprint=None):
    connection = connection or _default_connection(provider_dir)
    return connection, fingerprint or accounts.prepare(connection)[1]


def _cache_path(provider_dir, connection=None, fingerprint=None):
    _, fingerprint = _cache_context(provider_dir, connection, fingerprint)
    return os.path.join(CACHE_DIR, f"{fingerprint}.json")


def _save_cache(provider_dir, data, connection=None, fingerprint=None):
    try:
        connection, fingerprint = _cache_context(provider_dir, connection, fingerprint)
        os.makedirs(CACHE_DIR, exist_ok=True, mode=0o700)
        path = _cache_path(provider_dir, connection, fingerprint)
        paths.atomic_json(path, {"timestamp": time.time(), "connection_id": connection["connection_id"],
                                "fingerprint": fingerprint, "data": data})
    except Exception:
        pass

def _load_cache(provider_dir, connection=None, fingerprint=None, ttl=CACHE_TTL):
    try:
        connection, fingerprint = _cache_context(provider_dir, connection, fingerprint)
        path = _cache_path(provider_dir, connection, fingerprint)
        with open(path, encoding="utf-8") as f:
            cache = json.load(f)
        if (cache.get("connection_id") == connection["connection_id"] and cache.get("fingerprint") == fingerprint
                and 0 <= time.time() - cache.get("timestamp", 0) < ttl):
            data = cache["data"]
            if ttl == MIN_REFRESH_SECONDS:
                # A response from before an expected reset cannot confirm that
                # capacity is back. Re-query even inside the request coalescing
                # interval; failures still respect the vendor's cooldown.
                now = time.time()
                for entry in data if isinstance(data, list) else [data]:
                    if not isinstance(entry, dict):
                        continue
                    observed = entry.get("_observed_at", cache.get("timestamp", 0))
                    for metric in entry.get("metrics", []):
                        deadline = metric.get("reset_at")
                        if type(deadline) in (int, float) and type(observed) in (int, float) and observed < deadline <= now:
                            return None
            return data
    except Exception:
        pass
    return None

def _is_error_result(result):
    if result is None:
        return True
    if isinstance(result, list):
        return all(_is_error_result(item) for item in result)
    if isinstance(result, dict):
        if "error" in result or result.get("_error") and not result.get("_cached"):
            return True
        source = result.get("metrics")
        metrics = [metric for metric in source if isinstance(metric, dict)] if isinstance(source, list) else []
        if not metrics:
            return not usage_credits.has_credit_data(result)
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


def _cached_or_error(provider_dir, message, connection=None, fingerprint=None, secrets=(), use_cache=True):
    message = accounts.redact(message, secrets)
    cached = _load_cache(provider_dir, connection, fingerprint) if use_cache else None
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


def run_provider(provider_dir, connection=None):
    query_script = os.path.join(provider_dir, "query.py")
    if not os.path.exists(query_script):
        query_script = os.path.join(provider_dir, "query.sh")
    parse_script = os.path.join(provider_dir, "parse.py")

    if not os.path.exists(query_script):
        return {"error": "This provider collector is unavailable."} if connection else None

    connection = connection or _default_connection(provider_dir)
    try:
        env, fingerprint, secrets = accounts.prepare(connection)
    except accounts.AccountError as error:
        # Incomplete credentials must never fall back to another connection's
        # inherited credentials or previously cached usage.
        return {"error": str(error)}
    # The default agy CLI can use an OS-keyring session that is absent from
    # credential files. Without a verifiable identity, cached usage could
    # belong to a previous login. Explicit files/tokens have safe fingerprints.
    use_cache = not (connection["provider"] == "antigravity" and not connection.get("auth_file")
                     and not env.get("ANTIGRAVITY_ACCESS_TOKEN"))
    remaining = _cooldown_remaining(connection, fingerprint)
    if remaining:
        return _cached_or_error(provider_dir, _rate_limit_message(remaining), connection, fingerprint, secrets, use_cache)
    fresh = _load_cache(provider_dir, connection, fingerprint, ttl=MIN_REFRESH_SECONDS) if use_cache else None
    if fresh:
        return fresh
    try:
        env["PYTHONPATH"] = os.path.dirname(cfgmod.providers_dir()) + os.pathsep + env.get("PYTHONPATH", "")
        env["PYTHONIOENCODING"] = "utf-8"
        notification_identity = accounts.notification_identity(connection, env, fingerprint)
        options = {"creationflags": subprocess.CREATE_NO_WINDOW} if paths.IS_WINDOWS else {}
        with _service_lock(connection["provider"]):
            # Another caller may have received a 429 while this connection was
            # queued for its vendor's request slot.
            remaining = _cooldown_remaining(connection, fingerprint)
            if remaining:
                return _cached_or_error(provider_dir, _rate_limit_message(remaining), connection, fingerprint, secrets, use_cache)
            fresh = _load_cache(provider_dir, connection, fingerprint, ttl=MIN_REFRESH_SECONDS) if use_cache else None
            if fresh:
                return fresh
            _pace_service(connection["provider"])
            res = subprocess.run(query_command(query_script), capture_output=True, text=True,
                                 encoding="utf-8", errors="replace", env=env, timeout=40, **options)
            raw_output = res.stdout.strip()
            if raw_output.startswith("{"):
                try:
                    payload = json.loads(raw_output)
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and payload.get("_ai_status_status") == 429:
                    remaining = _save_cooldown(connection, fingerprint, payload.get("_ai_status_retry_after", 300))
                    return _cached_or_error(provider_dir, _rate_limit_message(remaining), connection, fingerprint, secrets, use_cache)
        if res.returncode != 0:
            return _cached_or_error(provider_dir, "Query failed; check authentication and CLI compatibility.", connection, fingerprint, secrets, use_cache)

        if not raw_output:
            return _cached_or_error(provider_dir, "No usage returned; check authentication.", connection, fingerprint, secrets, use_cache)

        if raw_output.startswith("{"):
            try:
                message = json.loads(raw_output).get("_ai_status_error")
            except (ValueError, AttributeError):
                message = None
            if message:
                return _cached_or_error(provider_dir, message, connection, fingerprint, secrets, use_cache)

        if os.path.exists(parse_script):
            spec = importlib.util.spec_from_file_location("parse", parse_script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            result = module.parse(raw_output)
        else:
            result = json.loads(raw_output)

        result = accounts.redact(result, secrets)
        if _is_error_result(result):
            return _cached_or_error(provider_dir, _extract_error_detail(result), connection, fingerprint, secrets, use_cache)

        observed = time.time()
        for entry in result if isinstance(result, list) else [result]:
            if not isinstance(entry, dict):
                continue
            entry["_observed_at"] = observed
            entry["_fingerprint"] = fingerprint
            entry["_notification_identity"] = notification_identity
            for metric in entry.get("metrics", []):
                remaining = metric.get("reset_in_seconds")
                if "reset_at" not in metric and type(remaining) in (int, float) and math.isfinite(remaining) and remaining > 0:
                    metric["reset_at"] = observed + remaining
        if use_cache:
            _save_cache(provider_dir, result, connection, fingerprint)
        return result

    except subprocess.TimeoutExpired:
        return _cached_or_error(provider_dir, "Usage query timed out.", connection, fingerprint, secrets, use_cache)
    except Exception:
        return _cached_or_error(provider_dir, "Unable to read usage; check credentials and provider response format.", connection, fingerprint, secrets, use_cache)

_latest_version = None
_latest_release_notes = None


def stable_version(value):
    """Comparable stable SemVer; release branches and prereleases are excluded."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", value)
    return tuple(int(part) for part in match.groups()) if match else None


def newer_version(latest, current):
    latest_parts, current_parts = stable_version(latest), stable_version(current)
    return latest_parts is not None and current_parts is not None and latest_parts > current_parts


def _release_notes(data, tag):
    """Keep the GitHub body used by the website; malformed notes never leak out."""
    body = data.get("body")
    if body is None or isinstance(body, str) and not body.strip():
        return None
    name, url, published = data.get("name"), data.get("html_url"), data.get("published_at")
    if (not isinstance(body, str) or name is not None and not isinstance(name, str)
            or not isinstance(url, str) or any(ord(character) <= 32 or ord(character) == 127 for character in url)
            or not isinstance(published, str)):
        return None
    try:
        location = urlsplit(url)
        if (location.scheme != "https" or location.hostname != "github.com" or location.username is not None
                or location.port not in (None, 443) or location.query or location.fragment
                or location.path != "/gelzinn/ai-status/releases/tag/" + tag):
            return None
        datetime.fromisoformat(published.replace("Z", "+00:00"))
    except ValueError:
        return None

    # Match markdown.tsx's releaseHeading: only a redundant first H2 with a
    # version link and the publication date is removed. Keep every other note,
    # heading, link, image and code block as authored on GitHub.
    version, date = tag[1:], published[:10]
    heading = re.match(
        r"\A(?:[ \t]*\r?\n)*[ ]{0,3}##[ \t]+\[" + re.escape(version)
        + r"\]\(<?(?P<url>https://github\.com/[^\s)>]+)>?\)[ \t]+\(" + re.escape(date)
        + r"\)[ \t]*(?:[ \t]+#+[ \t]*)?(?:\r?\n|$)", body)
    if heading and ("/compare/" in heading["url"] or heading["url"].endswith("/commits/" + tag)):
        body = body[heading.end():].lstrip("\r\n")
    if not body.strip():
        return None
    return {"version": version, "title": name.strip() if name and name.strip() else tag,
            "body": body, "url": url}


def get_release_notes(latest):
    """Read cached notes without I/O; never associate them with another release."""
    notes = _latest_release_notes
    if stable_version(latest) is None or not notes or notes["version"] != latest.removeprefix("v"):
        return None
    return dict(notes)


def check_for_updates():
    global _latest_version, _latest_release_notes
    try:
        data = json.loads(request(
            "https://api.github.com/repos/gelzinn/ai-status/releases/latest",
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ai-status",
            },
            timeout=5,
        ))
        tag = data.get("tag_name", "") if isinstance(data, dict) else None
        if (not isinstance(data, dict) or any(type(data.get(flag, False)) is not bool for flag in ("draft", "prerelease"))
                or data.get("draft") or data.get("prerelease") or not isinstance(tag, str)
                or not tag.startswith("v") or stable_version(tag) is None):
            _latest_version = None
            _latest_release_notes = None
            return
        # Notes are optional: a malformed body must not hide a valid version.
        # A failed request/JSON read keeps the previous good response in memory.
        _latest_release_notes = _release_notes(data, tag)
        _latest_version = tag[1:]
        return _latest_version
    except Exception:
        return None

def get_version_info():
    return {
        "current": __version__,
        "latest": _latest_version,
        "has_update": newer_version(_latest_version, __version__),
    }

def fetch_all_data(on_result=None, on_error=None, include_errors=False, check_updates=False):
    repo_dir = cfgmod.providers_dir()
    script_dir = repo_dir

    if not os.path.exists(script_dir):
        return []

    try:
        connections = cfgmod.enabled_connections()
    except accounts.AccountError as error:
        if on_error:
            on_error("accounts", str(error))
        # A malformed accounts file must not stop the existing default sessions.
        connections = [_default_connection(os.path.join(script_dir, name)) for name in cfgmod.enabled_order()
                       if name in cfgmod.available_providers()]

    connection_results = {}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(connections))) + int(check_updates)) as executor:
        if check_updates:
            # Check the release alongside usage queries. A slow or unavailable
            # GitHub response must not delay streamed provider results.
            executor.submit(check_for_updates)
        future_to_connection = {}
        for connection in connections:
            directory = os.path.join(script_dir, connection["provider"])
            # Preserve the one-argument entry point for existing integrations.
            future = (executor.submit(run_provider, directory, connection) if connection.get("account_id")
                      else executor.submit(run_provider, directory))
            future_to_connection[future] = connection
        for future in as_completed(future_to_connection):
            connection = future_to_connection[future]
            dir_name = connection["provider"]
            identity = connection["connection_id"]
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
                            p["_connection_id"] = identity
                            p["_account_id"] = connection.get("account_id")
                            if connection.get("account_id"):
                                p["_account_label"] = connection.get("label", connection["account_id"])
                    connection_results[identity] = providers
                elif on_error:
                    on_error(identity, (data or {}).get("error", "No usage available."))
            except Exception:
                providers = None
                if on_error:
                    on_error(identity, "Unable to read usage.")
            # Report each provider the moment it finishes so callers can render
            # incrementally instead of waiting for the slowest one.
            if on_result:
                on_result(identity, providers)

    results = []
    for connection in connections:
        if connection["connection_id"] in connection_results:
            results.extend(connection_results[connection["connection_id"]])
    return results
