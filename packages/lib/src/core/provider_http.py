"""Standard-library collectors: no Bash, jq or curl required."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.error
import urllib.request


class QueryError(Exception):
    """An actionable, credential-free message safe to show in the dashboard."""


def request(url, headers=None, timeout=8):
    headers = {"User-Agent": "ai-status", **(headers or {})}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise QueryError(f"Usage request returned HTTP {exc.code}; check your session.") from None
    except (urllib.error.URLError, OSError):
        raise QueryError("Usage API unreachable; check your connection.") from None


def output(query):
    try:
        result = query()
        if result is not None:
            print(result if isinstance(result, str) else json.dumps(result))
    except QueryError as exc:
        print(json.dumps({"_ai_status_error": str(exc)}))


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
