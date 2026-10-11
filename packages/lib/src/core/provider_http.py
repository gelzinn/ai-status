"""Standard-library collectors: no Bash, jq or curl required."""
import json
import ipaddress
from datetime import timezone
from email.utils import parsedate_to_datetime
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import paths


class QueryError(Exception):
    """An actionable, credential-free message safe to show in the dashboard."""
    def __init__(self, message, status=None, retry_after_seconds=None):
        super().__init__(message)
        self.status = status
        self.retry_after_seconds = retry_after_seconds


def retry_after_seconds(value, now=None):
    """Respect server cooling-off windows with a bounded safe fallback."""
    seconds = 300
    if isinstance(value, str):
        try:
            stripped = value.strip()
            if stripped.isdigit():
                seconds = int(stripped)
            else:
                end = parsedate_to_datetime(stripped)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=timezone.utc)
                seconds = math.ceil(end.timestamp() - (time.time() if now is None else now))
        except (ValueError, TypeError, OverflowError):
            pass
    return max(1, min(seconds, 86400))


def _http_error(code, retry_after=None):
    if code == 429:
        seconds = retry_after_seconds(retry_after)
        return QueryError(f"Usage API rate limited (HTTP 429); retry in {seconds}s.", status=429, retry_after_seconds=seconds)
    return QueryError(f"Usage request returned HTTP {code}; check your session.", status=code)


def _origin(url):
    """HTTPS for remote APIs; HTTP is reserved for loopback CLI/tests."""
    if not isinstance(url, str) or any(c in url for c in "\r\n\0"):
        raise QueryError("Invalid usage API URL.")
    try:
        parts = urlsplit(url)
        port = parts.port or (443 if parts.scheme == "https" else 80)
        hostname = parts.hostname
        if not hostname or parts.username is not None or not 0 < port <= 65535:
            raise ValueError
        loopback = hostname.lower() == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if parts.scheme != "https" and not (parts.scheme == "http" and loopback):
            raise ValueError
        return parts.scheme, hostname.lower(), port
    except ValueError:
        raise QueryError("Usage API requires HTTPS; HTTP is only permitted on localhost.") from None


class _UsageRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.get_method() != "GET" or req.data is not None:
            raise QueryError("Usage API redirected a request body; refusing to forward credentials.")
        origin, destination = _origin(req.full_url), _origin(newurl)
        if origin[0] == "https" and destination[0] != "https":
            raise QueryError("Usage API returned an insecure redirect.")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and destination != origin:
            for name in list(redirected.headers):
                if name.lower() not in {"user-agent", "accept", "accept-language"}:
                    redirected.remove_header(name)
        return redirected


def request_bytes(url, headers=None, timeout=8, method="GET", data=None):
    _origin(url)
    headers = {"User-Agent": "ai-status", **(headers or {})}
    if paths.IS_WINDOWS:
        from . import windows_http
        try:
            if method == "GET" and data is None:
                return windows_http.request(url, headers, timeout)
            return windows_http.request(url, headers, timeout, method=method, data=data)
        except windows_http.HTTPError as exc:
            raise _http_error(exc.code, exc.retry_after) from None
        except (OSError, ValueError):
            raise QueryError("Usage API unreachable; check your connection.") from None
    req = urllib.request.Request(url, headers=headers, method=method, data=data)
    try:
        with urllib.request.build_opener(_UsageRedirects()).open(req, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise _http_error(exc.code, exc.headers.get("Retry-After") if exc.headers else None) from None
    except (urllib.error.URLError, OSError):
        raise QueryError("Usage API unreachable; check your connection.") from None


def request(url, headers=None, timeout=8, method="GET", data=None):
    return request_bytes(url, headers, timeout, method=method, data=data).decode("utf-8")


def output(query):
    try:
        result = query()
        if result is not None:
            print(result if isinstance(result, str) else json.dumps(result))
    except QueryError as exc:
        result = {"_ai_status_error": str(exc)}
        if exc.status is not None:
            result["_ai_status_status"] = exc.status
        if exc.retry_after_seconds is not None:
            result["_ai_status_retry_after"] = exc.retry_after_seconds
        print(json.dumps(result))


def require_token(token, instructions):
    if not isinstance(token, str) or not token:
        raise QueryError(instructions)
    return token


def cli_path(name):
    executable = shutil.which(name)
    if executable:
        return executable
    if os.name == "nt":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        for candidate in (local / name / "bin" / (name + ".exe"),
                          Path.home() / ".local/bin" / (name + ".exe")):
            if candidate.is_file():
                return str(candidate)
    raise QueryError(f"{name} is not installed or is not on PATH; install and sign in to its native CLI.")


def run_cli(args, timeout=8):
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, **options)
    except (OSError, subprocess.TimeoutExpired):
        raise QueryError("CLI could not run or timed out; check its native installation.") from None
    if result.returncode:
        raise QueryError("CLI query failed; sign in again and verify the installed CLI version.")
    return result.stdout
