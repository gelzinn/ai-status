"""CLI logins found in config folders, offered as account connections without setup.

Claude Code, Codex and Command Code keep one account per config folder. Extra
accounts live next to the default one, run with CLAUDE_CONFIG_DIR or
CODEX_HOME: ~/.claude-<name> by hand, or ~/.config/seats/<tool>/<name> when a
tool such as seats manages them. Each signed-in folder becomes an account
record. Nothing is written: the ID comes from the account itself, so a renamed
or moved folder keeps its connection.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import time

from . import paths

_TTL = 5
# Copies left next to real folders: backups, stubs and lock folders.
_IGNORED = (".bak", ".lock", "backup", "stub", ".pre-share")
_memo = {}
_identities = {}


def _jwt_claims(token):
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (AttributeError, IndexError, ValueError):
        return {}
    return claims if isinstance(claims, dict) else {}


def _claude_account(meta_file):
    """`oauthAccount` from a `.claude.json`, which also holds project history: parsed once per change."""
    try:
        stat = meta_file.stat()
        version = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}
    cached = _identities.get(str(meta_file))
    if cached and cached[0] == version:
        return cached[1]
    meta = paths.read_json(meta_file)
    account = meta.get("oauthAccount") if isinstance(meta, dict) else None
    account = ({key: value for key, value in account.items()
                if key in ("accountUuid", "emailAddress") and isinstance(value, str)}
               if isinstance(account, dict) else {})
    _identities[str(meta_file)] = (version, account)
    return account


def _claude_login(directory, home, plain):
    stored = paths.read_json(directory / ".credentials.json")
    oauth = stored.get("claudeAiOauth") if isinstance(stored, dict) else None
    if not isinstance(oauth, dict) or not isinstance(oauth.get("accessToken"), str) or not oauth["accessToken"]:
        return None
    meta_file = directory / ".claude.json"
    if plain and not meta_file.exists():
        # Claude Code run without CLAUDE_CONFIG_DIR keeps its account in ~/.claude.json.
        meta_file = home / ".claude.json"
    account = _claude_account(meta_file)
    expiry = oauth.get("expiresAt")
    return {"anchor": account.get("accountUuid") or account.get("emailAddress"),
            "email": account.get("emailAddress"),
            "freshness": expiry if isinstance(expiry, (int, float)) else 0}


def _codex_login(directory, home, plain):
    stored = paths.read_json(directory / "auth.json")
    tokens = stored.get("tokens") if isinstance(stored, dict) else None
    if not isinstance(tokens, dict) or not isinstance(tokens.get("access_token"), str) or not tokens["access_token"]:
        return None
    claims = _jwt_claims(tokens.get("id_token"))
    auth = claims.get("https://api.openai.com/auth")
    auth = auth if isinstance(auth, dict) else {}
    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    # One ChatGPT workspace holds many people: the user and the workspace together name the account.
    user = auth.get("chatgpt_user_id") or claims.get("sub") or email
    workspace = tokens.get("account_id") or auth.get("chatgpt_account_id") or ""
    refreshed = stored.get("last_refresh")
    return {"anchor": f"{user}/{workspace}" if user else None, "email": email,
            "freshness": refreshed if isinstance(refreshed, str) else ""}


def _commandcode_login(directory, home, plain):
    stored = paths.read_json(directory / "auth.json")
    key = stored.get("apiKey") if isinstance(stored, dict) else None
    if not isinstance(key, str) or not key:
        return None
    # The file holds only the key, so a one-way digest of it stands for the account.
    return {"anchor": "key:" + hashlib.sha256(key.encode()).hexdigest(), "email": None, "freshness": 0}


# provider: (default folder under home, variable that moves it, credential file, reader)
PROVIDERS = {
    "claude": (".claude", "CLAUDE_CONFIG_DIR", ".credentials.json", _claude_login),
    "codex": (".codex", "CODEX_HOME", "auth.json", _codex_login),
    "commandcode": (".commandcode", None, "auth.json", _commandcode_login),
}


def _roots(provider, environ):
    live, variable, _, _ = PROVIDERS[provider]
    home = Path(environ.get("HOME") or environ.get("USERPROFILE") or Path.home())
    # seats keeps its folders here regardless of XDG_CONFIG_HOME.
    seats = Path(environ.get("SEATS_HOME") or home / ".config/seats").expanduser()
    default = Path((variable and environ.get(variable)) or home / live).expanduser()
    return home, seats, default


def _candidates(provider, environ):
    home, seats, default = _roots(provider, environ)
    live = PROVIDERS[provider][0]
    found = [default, home / live]
    for parent, pattern in ((home, live + "-*"), (seats / provider, "*")):
        try:
            found.extend(sorted(path for path in parent.glob(pattern)
                                if path.is_dir() and not any(mark in path.name for mark in _IGNORED)))
        except OSError:
            continue
    return found


def _real(path):
    try:
        return os.path.realpath(os.path.expanduser(path))
    except (OSError, ValueError):
        return None


def _label(provider, directory, email):
    if email:
        return email
    live = PROVIDERS[provider][0]
    name = directory.name
    return name[len(live) + 1:] if name.startswith(live + "-") else name


def _discover(provider, taken, skip_default, environ):
    home, _, default = _roots(provider, environ)
    live, _, credential, read = PROVIDERS[provider]
    # The default connection reads `default`. Listing it too would show the account twice;
    # when that connection is off, a real folder stays off, but a link into a store (one
    # seat of several, as seats sets up) is listed like the other seats.
    skipped = {_real(default)} if skip_default or not os.path.islink(default) else set()
    plain = _real(home / live)
    seen_dirs, best = set(), {}
    for directory in _candidates(provider, environ):
        real = _real(directory)
        if not real or real in seen_dirs:
            continue
        seen_dirs.add(real)
        credentials = os.path.join(real, credential)
        if real in skipped or _real(credentials) in taken:
            continue
        login = read(Path(real), home, real == plain)
        if login is None:
            continue
        anchor = login["anchor"] or real
        account_id = f"{provider}-" + hashlib.sha256(str(anchor).encode()).hexdigest()[:10]
        # The same account in two folders: keep the one its CLI refreshed last.
        if account_id in best and best[account_id][0] >= login["freshness"]:
            continue
        best[account_id] = (login["freshness"], {
            "id": account_id, "provider": provider, "label": _label(provider, directory, login["email"]),
            "enabled": True, "env": {}, "options": {}, "auth_file": credentials, "discovered": True})
    return sorted((record for _, record in best.values()), key=lambda record: record["label"].lower())


def discover(saved=(), *, enabled=(), environ=None):
    """Account records for CLI logins found in config folders, one per account.

    Skips credential files a saved account points at, and the folder each
    default connection reads when that provider is in `enabled`.
    """
    environ = os.environ if environ is None else environ
    records = []
    for provider, (_, variable, _, _) in PROVIDERS.items():
        taken = {_real(record["auth_file"]) for record in saved
                 if record.get("provider") == provider and record.get("auth_file")}
        signature = (provider, tuple(sorted(filter(None, taken))), provider in enabled,
                     environ.get("HOME"), environ.get("USERPROFILE"), environ.get("SEATS_HOME"),
                     variable and environ.get(variable))
        cached = _memo.get(signature)
        if not cached or time.monotonic() - cached[0] >= _TTL:
            cached = (time.monotonic(), _discover(provider, taken, provider in enabled, environ))
            _memo[signature] = cached
        records.extend(dict(record) for record in cached[1])
    return records
