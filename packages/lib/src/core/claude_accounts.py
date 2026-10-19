"""Claude Code logins found on disk, offered as account connections without setup.

Extra Claude Code accounts live in their own config folders, run with
CLAUDE_CONFIG_DIR: ~/.claude-<name> by hand, or ~/.config/seats/claude/<name>
when a tool such as seats manages them. Each folder with a signed-in
.credentials.json becomes an account record. Nothing is written: the ID comes
from the account itself, so a renamed or moved folder keeps its connection.
"""
import hashlib
import os
from pathlib import Path
import time

from . import paths

_TTL = 5
# Copies left next to real folders: backups, stubs and lock folders.
_IGNORED = (".bak", ".lock", "backup", "stub", ".pre-share")
_memo = {}
_identities = {}


def _roots(environ):
    home = Path(environ.get("HOME") or environ.get("USERPROFILE") or Path.home())
    # seats keeps its folders here regardless of XDG_CONFIG_HOME.
    seats = Path(environ.get("SEATS_HOME") or home / ".config/seats").expanduser()
    default = Path(environ.get("CLAUDE_CONFIG_DIR") or home / ".claude").expanduser()
    return home, seats, default


def _candidates(environ):
    home, seats, default = _roots(environ)
    found = [default, home / ".claude"]
    for parent, pattern in ((home, ".claude-*"), (seats / "claude", "*")):
        try:
            found.extend(sorted(path for path in parent.glob(pattern)
                                if path.is_dir() and not any(mark in path.name for mark in _IGNORED)))
        except OSError:
            continue
    return found


def _expiry(directory):
    """When the folder's access token expires (0 if unknown), or None when it holds no login."""
    stored = paths.read_json(directory / ".credentials.json")
    oauth = stored.get("claudeAiOauth") if isinstance(stored, dict) else None
    if not isinstance(oauth, dict) or not isinstance(oauth.get("accessToken"), str) or not oauth["accessToken"]:
        return None
    expiry = oauth.get("expiresAt")
    return expiry if isinstance(expiry, (int, float)) else 0


def _identity(directory):
    """A stable ID and label for the account signed in to `directory`."""
    meta_file = directory / ".claude.json"
    try:
        stat = meta_file.stat()
        key = (str(meta_file), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None
    if key is None or key not in _identities:
        # .claude.json also holds project history and can be large; parse it once per change.
        meta = paths.read_json(meta_file)
        account = meta.get("oauthAccount") if isinstance(meta, dict) else None
        account = account if isinstance(account, dict) else {}
        email = account.get("emailAddress") if isinstance(account.get("emailAddress"), str) else None
        anchor = account.get("accountUuid") or email or str(directory.resolve())
        result = ("claude-" + hashlib.sha256(str(anchor).encode()).hexdigest()[:10], email)
        if key is None:
            return result
        _identities[key] = result
    return _identities[key]


def _real(path):
    try:
        return os.path.realpath(os.path.expanduser(path))
    except (OSError, ValueError):
        return None


def discover(saved=(), *, skip_default=True, environ=None):
    """Account records for Claude logins on disk, one per account.

    Skips the folder the default Claude connection already reads when
    `skip_default`, and credential files a saved account points at.
    """
    environ = os.environ if environ is None else environ
    _, _, default = _roots(environ)
    taken = {_real(record["auth_file"]) for record in saved
             if record.get("provider") == "claude" and record.get("auth_file")}
    signature = (tuple(sorted(filter(None, taken))), skip_default,
                 environ.get("HOME"), environ.get("USERPROFILE"), environ.get("SEATS_HOME"),
                 environ.get("CLAUDE_CONFIG_DIR"))
    cached = _memo.get(signature)
    if cached and time.monotonic() - cached[0] < _TTL:
        return [dict(record) for record in cached[1]]

    skipped = {_real(default)} if skip_default else set()
    seen_dirs, best = set(), {}
    for directory in _candidates(environ):
        real = _real(directory)
        if not real or real in seen_dirs:
            continue
        seen_dirs.add(real)
        expiry = None if real in skipped else _expiry(directory)
        credentials = os.path.join(real, ".credentials.json")
        if expiry is None or _real(credentials) in taken:
            continue
        account_id, email = _identity(Path(real))
        # The same account in two folders: keep the one its CLI refreshed last.
        if account_id in best and best[account_id][0] >= expiry:
            continue
        best[account_id] = (expiry, {"id": account_id, "provider": "claude", "label": email or directory.name,
                                     "enabled": True, "env": {}, "options": {}, "auth_file": credentials,
                                     "discovered": True})
    records = sorted((record for _, record in best.values()), key=lambda record: record["label"].lower())
    _memo[signature] = (time.monotonic(), records)
    return [dict(record) for record in records]
