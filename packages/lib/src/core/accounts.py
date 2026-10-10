"""Saved account connections and per-process credential/context isolation.

Credential values are resolved only in memory. Saved environment overrides refer
to other environment variables or files, never literal secrets.
"""
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import sys
import sqlite3
from contextlib import closing

from . import paths

VERSION = 1
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_ENVIRONMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SECRET_KEY = re.compile(r"token|secret|password|cookie|credential|authorization|api.?key|^access$|^refresh$|^key$", re.I)
_LITERAL_SECRET_KEYS = {"apikey", "accesstoken", "refreshtoken", "token", "password", "cookie",
                        "authcookie", "clientsecret", "secret", "authorization", "key"}
_AUTH_ENVIRONMENT = {
    "codex": ("CODEX_ACCESS_TOKEN", "CODEX_ACCOUNT_ID", "CODEX_HOME"),
    "claude": ("CLAUDE_ACCESS_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY"),
    "copilot": ("GITHUB_COPILOT_TOKEN", "GH_TOKEN", "GITHUB_TOKEN", "GH_CONFIG_DIR"),
    "opencode": ("OPENCODE_GO_API_KEY", "OPENCODE_GO_AUTH_COOKIE", "OPENCODE_GO_WORKSPACE_ID"),
    "openai-api": ("OPENAI_ADMIN_KEY", "OPENAI_API_KEY", "OPENAI_ORG_ID"),
    "anthropic-api": ("ANTHROPIC_ADMIN_KEY", "ANTHROPIC_ADMIN_TOKEN", "ANTHROPIC_API_KEY"),
    "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_MANAGEMENT_KEY"),
    "google-cloud": ("GOOGLE_CLOUD_ACCESS_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS", "CLOUDSDK_CONFIG", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"),
    "grok": ("XAI_MANAGEMENT_KEY", "XAI_API_KEY"),
    "supergrok": ("SUPERGROK_ACCESS_TOKEN", "GROK_HOME"),
    "cursor": ("CURSOR_ACCESS_TOKEN",), "grok-bot": ("GROK_BOT_ACCESS_TOKEN",),
    "nous": ("NOUS_ACCESS_TOKEN",), "modelstudio": ("MODELSTUDIO_ACCESS_TOKEN",),
    "kiro": ("KIRO_ACCESS_TOKEN",), "antigravity": ("ANTIGRAVITY_ACCESS_TOKEN",),
}
_CONTEXT_ENVIRONMENT = {"HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                        "XDG_CACHE_HOME", "PATH", "PYTHONPATH", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
                        "NO_PROXY", "http_proxy", "https_proxy", "all_proxy", "no_proxy", "LANG", "LC_ALL"}


def _validate_options(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if re.sub(r"[^a-z]", "", str(key).lower()) in _LITERAL_SECRET_KEYS:
                raise AccountError("Store credentials in environment or file references, not account options.")
            if str(key).endswith("_env") and (not isinstance(item, str) or not _ENVIRONMENT.fullmatch(item)):
                raise AccountError("Account environment references must name an environment variable.")
            _validate_options(item)
    elif isinstance(value, list):
        for item in value:
            _validate_options(item)


class AccountError(ValueError):
    """An account configuration error whose message contains no secret values."""


def normalize(record):
    if not isinstance(record, dict):
        raise AccountError("Each account must be a JSON object.")
    allowed = {"id", "provider", "label", "enabled", "env", "options", "auth_file"}
    if set(record) - allowed:
        raise AccountError("Account configuration contains unsupported fields.")
    result = dict(record)
    for key in ("id", "provider"):
        if not isinstance(result.get(key), str) or not _IDENTIFIER.fullmatch(result[key]):
            raise AccountError(f"Account {key} must use letters, numbers, dots, underscores or hyphens.")
    result.setdefault("label", result["id"])
    if not isinstance(result["label"], str) or not result["label"].strip():
        raise AccountError("Account label must be a nonempty string.")
    result.setdefault("enabled", True)
    if not isinstance(result["enabled"], bool):
        raise AccountError("Account enabled must be true or false.")
    result.setdefault("options", {})
    if not isinstance(result["options"], dict):
        raise AccountError("Account options must be a JSON object.")
    _validate_options(result["options"])
    try:
        json.dumps(result["options"], allow_nan=False)
    except (ValueError, TypeError):
        raise AccountError("Account options must contain valid JSON values.") from None
    result.setdefault("env", {})
    if not isinstance(result["env"], dict):
        raise AccountError("Account env must be a JSON object of credential references.")
    normalized_env = {}
    for key, source in result["env"].items():
        if not isinstance(key, str) or not _ENVIRONMENT.fullmatch(key) or key.startswith("AI_STATUS_"):
            raise AccountError("Account environment variable name is invalid or reserved.")
        if isinstance(source, str):
            source = {"from_env": source}
        if not isinstance(source, dict) or len(source) != 1:
            raise AccountError("Environment overrides must refer to from_env or from_file.")
        if "from_env" in source:
            if not isinstance(source["from_env"], str) or not _ENVIRONMENT.fullmatch(source["from_env"]):
                raise AccountError("Credential source must name an environment variable.")
        elif "from_file" in source:
            if not isinstance(source["from_file"], str) or not source["from_file"]:
                raise AccountError("Credential source must name a file.")
        else:
            raise AccountError("Literal environment values are unsupported; use from_env or from_file.")
        normalized_env[key] = dict(source)
    result["env"] = normalized_env
    if "auth_file" in result and (not isinstance(result["auth_file"], str) or not result["auth_file"]):
        raise AccountError("Account auth_file must name a file.")
    return result


def load_document(path=None):
    path = Path(path or paths.CONFIG_DIR / "accounts.json")
    if not path.exists():
        return {"version": VERSION, "accounts": []}
    try:
        with path.open(encoding="utf-8-sig") as stream:
            document = json.load(stream)
    except (OSError, ValueError):
        raise AccountError("Unable to read accounts.json; check its JSON format and permissions.") from None
    if not isinstance(document, dict) or document.get("version") != VERSION or not isinstance(document.get("accounts"), list):
        raise AccountError("accounts.json must contain version 1 and an accounts array.")
    records = [normalize(record) for record in document["accounts"]]
    if len({record["id"] for record in records}) != len(records):
        raise AccountError("Account IDs must be unique.")
    result = {"version": VERSION, "accounts": records}
    if "order" in document:
        order = document["order"]
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order) or len(set(order)) != len(order):
            raise AccountError("Account connection order must contain unique connection IDs.")
        result["order"] = order
    return result


def save_document(document, path=None):
    # Validate before replacing a previously working configuration.
    records = [normalize(record) for record in document.get("accounts", [])]
    if len({record["id"] for record in records}) != len(records):
        raise AccountError("Account IDs must be unique.")
    result = {"version": VERSION, "accounts": records}
    if "order" in document:
        order = document["order"]
        if not isinstance(order, list) or any(not isinstance(item, str) for item in order) or len(set(order)) != len(order):
            raise AccountError("Account connection order must contain unique connection IDs.")
        result["order"] = order
    path = Path(path or paths.CONFIG_DIR / "accounts.json")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    paths.atomic_json(path, result)  # mkstemp creates a private 0600 file.


def connection(record):
    return {**record, "account_id": record["id"], "connection_id": "account:" + record["id"]}


def public_record(record):
    """List account metadata without printing credential or option values."""
    return {key: record[key] for key in ("id", "provider", "label", "enabled")} | {
        "env": record.get("env", {}), "option_keys": sorted(record.get("options", {})),
        **({"auth_file": record["auth_file"]} if "auth_file" in record else {}),
    }


def _path(value, environ):
    # Expand references using this connection's environment, not global state.
    value = re.sub(r"\$(\w+)|\$\{([^}]+)\}", lambda match: environ.get(match[1] or match[2], match[0]), value)
    if value == "~" or value.startswith("~/") or value.startswith("~\\"):
        home = environ.get("HOME") or environ.get("USERPROFILE") or str(Path.home())
        value = os.path.join(home, value[2:]) if len(value) > 1 else home
    return Path(os.path.expanduser(value))


def _credential_files(environ, provider, auth_file=None):
    home = Path(environ.get("HOME") or environ.get("USERPROFILE") or str(Path.home()))
    data = Path(environ.get("XDG_DATA_HOME", home / ".local/share"))
    config = Path(environ.get("XDG_CONFIG_HOME", home / ".config"))
    native_config = (Path(environ.get("APPDATA", home / "AppData/Roaming")) if paths.IS_WINDOWS
                     else home / "Library/Application Support" if sys.platform == "darwin" else config)
    gcloud = Path(environ.get("CLOUDSDK_CONFIG", config / "gcloud"))
    candidates = {
        "codex": [Path(environ.get("CODEX_HOME", home / ".codex")) / "auth.json"],
        "claude": [Path(environ.get("CLAUDE_CONFIG_DIR", home / ".claude")) / ".credentials.json", data / "opencode/auth.json"],
        "commandcode": [home / ".commandcode/auth.json"],
        "copilot": [data / "opencode/auth.json", Path(environ.get("GH_CONFIG_DIR", config / "gh")) / "hosts.yml"],
        "opencode": [data / "opencode/auth.json", config / "opencode-bar/opencode-go.json"],
        "zai": [data / "opencode/account.json"],
        "kiro": [data / "kiro-cli/data.sqlite3", home / ".aws/sso/cache"],
        "antigravity": [home / ".gemini/antigravity-cli/antigravity-oauth-token", native_config / "Antigravity/User/globalStorage/state.vscdb"],
        "kimi": [home / ".kimi-code/credentials/kimi-code.json", home / ".kimi-code/region"],
        "supergrok": [Path(environ.get("GROK_HOME", home / ".grok")) / "auth.json"],
        "cursor": [native_config / "Cursor/User/globalStorage/state.vscdb", native_config / "Cursor/auth.json",
                   native_config / "cursor/auth.json", home / ".cursor/auth.json"],
        "grok-bot": [native_config / "Grok Bot/sand-secrets.json", native_config / "Grok Bot/Local State"],
        "nous": [native_config / "ai-usagebar/credentials.json"],
        "modelstudio": [home / ".bailian/config.json"],
        "devin": [(native_config if paths.IS_WINDOWS else data) / "devin/credentials.toml"],
        "google-cloud": [gcloud / "credentials.db", gcloud / "access_tokens.db", gcloud / "active_config",
                         gcloud / "configurations", Path(environ["GOOGLE_APPLICATION_CREDENTIALS"]) if environ.get("GOOGLE_APPLICATION_CREDENTIALS") else gcloud / "application_default_credentials.json"],
    }.get(provider, [])
    if auth_file:
        candidates.append(Path(auth_file))
    return candidates


def _secret_values(value, key=""):
    if isinstance(value, dict):
        return [secret for name, item in value.items() for secret in _secret_values(item, str(name))]
    if isinstance(value, list):
        return [secret for item in value for secret in _secret_values(item, key)]
    if isinstance(value, str) and value and _SECRET_KEY.search(key):
        return [value]
    return []


def _sqlite_context(path, provider=None, account=None):
    """Read relevant auth rows from one live, read-only SQLite snapshot.

    Reading through SQLite includes committed WAL changes. Hashing the database
    or WAL bytes would also include chat/settings activity and defeat cooldowns.
    """
    context, secrets = {}, []
    rows = []
    if provider in (None, "kiro"):
        rows.extend((
            ("auth_kv", "kirocli:odic:token", ("access_token", "refresh_token", "region", "expires_at", "account_id", "profile_arn")),
            ("state", "api.codewhisperer.profile", ("arn",)),
        ))
    if provider in (None, "cursor"):
        rows.append(("ItemTable", "cursorAuth/accessToken", None))
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            connection.execute("BEGIN")
            for table, key, fields in rows:
                try:
                    row = connection.execute(f"SELECT value FROM {table} WHERE key=?", (key,)).fetchone()
                except sqlite3.Error:
                    row = None
                value = row[0] if row else None
                if isinstance(value, (str, bytes)):
                    try:
                        parsed = json.loads(value)
                        value = {field: parsed[field] for field in fields if field in parsed} if fields and isinstance(parsed, dict) else parsed
                    except (ValueError, UnicodeError):
                        if isinstance(value, bytes):
                            value = {"invalid_value_digest": hashlib.sha256(value).hexdigest()}
                context[f"{table}:{key}"] = value
                secrets.extend(_secret_values(value))
                if key == "cursorAuth/accessToken" and isinstance(value, str) and value:
                    secrets.append(value)
            if provider in (None, "google-cloud"):
                for table, columns in (("credentials", "account_id, value"), ("access_tokens", "account_id, access_token, rapt_token")):
                    try:
                        condition = " WHERE account_id=?" if account else ""
                        result = connection.execute(f"SELECT {columns} FROM {table}{condition} ORDER BY account_id", (account,) if account else ()).fetchall()
                        values = []
                        for row in result:
                            decoded = []
                            for value in row:
                                if isinstance(value, (str, bytes)):
                                    try:
                                        value = json.loads(value)
                                    except (ValueError, UnicodeError):
                                        if isinstance(value, bytes):
                                            value = value.decode("utf-8", errors="replace")
                                decoded.append(value)
                                secrets.extend(_secret_values(value))
                            if table == "access_tokens":
                                secrets.extend(value for value in decoded[1:] if isinstance(value, str) and value)
                            values.append(decoded)
                        context[table] = values
                    except sqlite3.Error:
                        context[table] = None
    except sqlite3.Error:
        return {"unreadable_database": True}, []
    return context, secrets


def _file_secrets(path, raw):
    if raw.startswith(b"SQLite format 3\0"):
        return _sqlite_context(path)[1]
    try:
        text = raw.decode("utf-8-sig").strip()
        if text.startswith("go-keyring-base64:"):
            text = base64.b64decode(text.split(":", 1)[1], validate=True).decode("utf-8")
        return _secret_values(json.loads(text))
    except (ValueError, UnicodeError):
        secrets = []
        text = raw.decode("utf-8", errors="ignore").strip()
        for match in re.finditer(r"(?m)^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*[:=]\s*[\"']?([^\"'\r\n#]+)", text):
            if _SECRET_KEY.search(match[1]) and match[2].strip():
                secrets.append(match[2].strip())
        return secrets


def prepare(connection, environ=None):
    """Return subprocess env, context digest, and values to redact from results."""
    env = dict(os.environ if environ is None else environ)
    # A parent collector context must never leak into another/default connection.
    for key in list(env):
        if key.startswith("AI_STATUS_ACCOUNT_") or key == "AI_STATUS_AUTH_FILE":
            del env[key]
    source_env = dict(env)
    for key, source in connection.get("options", {}).items():
        if key.endswith("_env") and (not isinstance(source, str) or not source_env.get(source)):
            raise AccountError("A referenced account environment variable is unset or empty.")
    if connection.get("account_id"):
        explicit_keys = set(connection.get("env", {}))
        retained = {value for key, value in connection.get("options", {}).items()
                    if key.endswith("_env") and isinstance(value, str)}
        if connection["provider"] == "google-cloud" and connection.get("options", {}).get("gcloud_account"):
            retained.add("CLOUDSDK_CONFIG")
        variable = connection["provider"].upper().replace("-", "_") + "_API_KEY"
        for key in (*_AUTH_ENVIRONMENT.get(connection["provider"], ()), variable):
            if key not in explicit_keys and key not in retained:
                env.pop(key, None)
    secrets = _secret_values(connection.get("options", {}))
    for key, source in connection.get("env", {}).items():
        if "from_env" in source:
            value = source_env.get(source["from_env"])
            if not value:
                raise AccountError("A referenced account environment variable is unset or empty.")
        else:
            try:
                value = _path(source["from_file"], env).read_text(encoding="utf-8-sig").strip()
            except (OSError, ValueError):
                raise AccountError("Unable to read a referenced account credential file.") from None
            if not value:
                raise AccountError("A referenced account credential file is empty.")
        env[key] = value
        # Path overrides can be displayed by providers and are not credentials.
        if not key.endswith(("_HOME", "_DIR", "_PATH")) and key not in ("HOME", "USERPROFILE"):
            secrets.append(value)
    auth_file = connection.get("auth_file")
    if auth_file:
        auth_file = str(_path(auth_file, env))
        if not Path(auth_file).is_file():
            raise AccountError("The account authentication file is missing or unreadable.")
        env["AI_STATUS_AUTH_FILE"] = auth_file
    if connection.get("account_id"):
        env["AI_STATUS_ACCOUNT_ID"] = connection["account_id"]
        env["AI_STATUS_ACCOUNT_OPTIONS"] = json.dumps(connection.get("options", {}), ensure_ascii=False, separators=(",", ":"))
    secrets.extend(value for key, value in env.items() if _SECRET_KEY.search(key) and value)
    prefix = connection["provider"].upper().replace("-", "_") + "_"
    context_keys = _CONTEXT_ENVIRONMENT | set(_AUTH_ENVIRONMENT.get(connection["provider"], ())) | set(connection.get("env", {}))
    context_keys.update(key for key in env if key.startswith(prefix))
    context_keys.update(value for key, value in connection.get("options", {}).items()
                        if key.endswith("_env") and isinstance(value, str))
    digest = hashlib.sha256()
    digest.update(json.dumps({"connection_id": connection["connection_id"], "provider": connection["provider"],
                             "env": {key: value for key, value in env.items() if key in context_keys},
                             "auth_file": auth_file, "options": connection.get("options", {})}, sort_keys=True,
                            ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    credential_files = _credential_files(env, connection["provider"], auth_file)
    if connection.get("account_id"):
        # Explicit accounts only inspect files the collector may use for that
        # connection. Unrelated native credential rotation must not invalidate
        # their cached usage or rate-limit cooldown.
        credential_files = [Path(auth_file)] if auth_file else []
        explicit_keys = set(connection.get("env", {}))
        for variable, filename in (("CODEX_HOME", "auth.json"), ("CLAUDE_CONFIG_DIR", ".credentials.json"), ("GH_CONFIG_DIR", "hosts.yml")):
            if variable in explicit_keys:
                credential_files.append(Path(env[variable]) / filename)
        if connection["provider"] == "google-cloud" and (connection.get("options", {}).get("gcloud_account") or "CLOUDSDK_CONFIG" in explicit_keys):
            credential_files.extend(_credential_files(env, "google-cloud"))
    credential_secrets = []
    for candidate in credential_files:
        files = sorted(path for path in candidate.iterdir() if path.is_file()) if candidate.is_dir() else [candidate]
        for path in files:
            digest.update(str(path).encode("utf-8"))
            try:
                with path.open("rb") as stream:
                    header = stream.read(16)
                if header == b"SQLite format 3\0":
                    context, values = _sqlite_context(path, connection["provider"], connection.get("options", {}).get("gcloud_account"))
                    digest.update(json.dumps(context, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
                    raw = header
                else:
                    raw = path.read_bytes()
                    digest.update(hashlib.sha256(raw).digest())
                    values = _file_secrets(path, raw)
                credential_secrets.extend(values)
                if not values and str(path) == auth_file and not raw.startswith(b"SQLite format 3\0"):
                    value = raw.decode("utf-8", errors="ignore").strip()
                    if value:
                        credential_secrets.append(value)
            except OSError:
                digest.update(b"missing-or-unreadable")
    if (connection["provider"] == "cursor" and not connection.get("account_id") and sys.platform == "darwin"
            and not env.get("CURSOR_ACCESS_TOKEN") and not credential_secrets):
        # The macOS Cursor CLI may keep its sole credential in the login
        # keychain. Include that identity so signing into another account can
        # never reuse the previous account's usage cache.
        from .oscrypt import _secret
        token = _secret(["/usr/bin/security", "find-generic-password", "-s", "cursor-access-token", "-a", "cursor-user", "-w"])
        digest.update(hashlib.sha256(token or b"missing-keychain-token").digest())
        if token:
            credential_secrets.append(token.decode("utf-8", errors="replace"))
    secrets.extend(credential_secrets)
    return env, digest.hexdigest(), sorted(set(secrets), key=len, reverse=True)


def redact(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, dict):
        return {key: redact(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    return value
