"""Read Claude Code's macOS login Keychain without modifying credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from .paths import read_json
from .provider_http import QueryError


def _usable(credentials):
    if not isinstance(credentials, dict) or not credentials.get("accessToken"):
        return False
    try:
        expiry = float(credentials.get("expiresAt") or 0)
        return expiry == 0 or expiry > time.time() * 1000
    except (TypeError, ValueError):
        return False


def claude_credentials(root, scoped=False):
    # Claude Code scopes non-default config directories to a distinct item.
    # Never fall back to another account's unscoped Keychain entry.
    service = "Claude Code-credentials"
    if scoped:
        directory = str(Path(root).expanduser().absolute())
        service += "-" + hashlib.sha256(directory.encode()).hexdigest()[:8]
    args = ["/usr/bin/security", "find-generic-password", "-s", service, "-w"]
    if os.environ.get("USER"):
        args += ["-a", os.environ["USER"]]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        raise QueryError("Could not read Claude Code's macOS Keychain. Unlock the login Keychain and refresh.") from None
    if result.returncode not in (0, 44):
        raise QueryError("Claude Code's macOS Keychain is locked or access was denied. Allow access and refresh.")
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            credentials = data.get("claudeAiOauth") if isinstance(data, dict) else None
            if _usable(credentials):
                return credentials
        except ValueError:
            pass
    data = read_json(Path(root) / ".credentials.json")
    return data.get("claudeAiOauth", {}) if isinstance(data, dict) else {}
