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


def _identity(directory, meta_file):
    """A stable ID and label for the account signed in to `directory`, from its `.claude.json`."""
    try:
        stat = meta_file.stat()
        version = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        version = None
    cached = _identities.get(str(meta_file))
    if version is not None and cached and cached[0] == version:
        return cached[1]
    # .claude.json also holds project history and can be large; parse it once per change.
    meta = paths.read_json(meta_file)
    account = meta.get("oauthAccount") if isinstance(meta, dict) else None
    account = account if isinstance(account, dict) else {}
    email = account.get("emailAddress") if isinstance(account.get("emailAddress"), str) else None
    anchor = account.get("accountUuid") or email or str(directory)
    result = ("claude-" + hashlib.sha256(str(anchor).encode()).hexdigest()[:10], email)
    if version is not None:
        _identities[str(meta_file)] = (version, result)
    return result


def _real(path):
    try:
        return os.path.realpath(os.path.expanduser(path))
    except (OSError, ValueError):
        return None


def discover(saved=(), *, skip_default=True, environ=None):
    """Account records for Claude logins on disk, one per account.

    Skips credential files a saved account points at, and the folder the
    default Claude connection reads: always when `skip_default`, otherwise only
    when it's a real folder, so a single account that was turned off stays off.
    A `~/.claude` linked into a store (one seat of several) is listed then.
    """
    environ = os.environ if environ is None else environ
    home, _, default = _roots(environ)
    taken = {_real(record["auth_file"]) for record in saved
             if record.get("provider") == "claude" and record.get("auth_file")}
    signature = (tuple(sorted(filter(None, taken))), skip_default,
                 environ.get("HOME"), environ.get("USERPROFILE"), environ.get("SEATS_HOME"),
                 environ.get("CLAUDE_CONFIG_DIR"))
    cached = _memo.get(signature)
    if cached and time.monotonic() - cached[0] < _TTL:
        return [dict(record) for record in cached[1]]

    skipped = {_real(default)} if skip_default or not os.path.islink(default) else set()
    plain = _real(home / ".claude")
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
        meta_file = Path(real) / ".claude.json"
        if real == plain and not meta_file.exists():
            # Claude Code run without CLAUDE_CONFIG_DIR keeps its account in ~/.claude.json.
            meta_file = home / ".claude.json"
        account_id, email = _identity(Path(real), meta_file)
        # The same account in two folders: keep the one its CLI refreshed last.
        if account_id in best and best[account_id][0] >= expiry:
            continue
        best[account_id] = (expiry, {"id": account_id, "provider": "claude", "label": email or directory.name,
                                     "enabled": True, "env": {}, "options": {}, "auth_file": credentials,
                                     "discovered": True})
    records = sorted((record for _, record in best.values()), key=lambda record: record["label"].lower())
    _memo[signature] = (time.monotonic(), records)
    return [dict(record) for record in records]
