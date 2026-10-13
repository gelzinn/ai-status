import hashlib
import json
import os
from pathlib import Path
from core.paths import read_json
from core.provider_http import QueryError, output, request, require_token
from core.reset_credits import count

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def _auth_document(path, env):
    if "AI_STATUS_RESET_AUTH_SNAPSHOTS" in env:
        from core.accounts import auth_document
        return auth_document(path, env)
    return read_json(path)


def authentication(env=None):
    """Capture one account's credentials without changing the process environment."""
    env = os.environ if env is None else env
    if env.get("AI_STATUS_ACCOUNT_ID") and not any(env.get(key) for key in ("AI_STATUS_AUTH_FILE", "CODEX_HOME", "CODEX_ACCESS_TOKEN")):
        raise QueryError("Set auth_file, CODEX_HOME or CODEX_ACCESS_TOKEN for this Codex account.")
    direct = env.get("CODEX_ACCESS_TOKEN")
    use_file = not direct or env.get("AI_STATUS_AUTH_FILE") or env.get("CODEX_HOME")
    tokens = {}
    if use_file:
        path = env.get("AI_STATUS_AUTH_FILE")
        if not path:
            configured_root = env.get("CODEX_HOME")
            home = env.get("HOME") or env.get("USERPROFILE")
            root = Path(configured_root) if configured_root else Path(home or Path.home()) / ".codex"
            path = root / "auth.json"
        stored = _auth_document(path, env)
        tokens = stored.get("tokens") if isinstance(stored, dict) else None
        tokens = tokens if isinstance(tokens, dict) else {}
    token = require_token(direct or tokens.get("access_token"), "Sign in to Codex with your ChatGPT account.")
    headers = {"Authorization": f"Bearer {token}"}
    account_id = env.get("CODEX_ACCOUNT_ID") or tokens.get("account_id")
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
    return headers


def query():
    headers = authentication()
    raw = request(USAGE_URL, headers, timeout=10)
    try:
        usage = json.loads(raw)
    except ValueError:
        return raw
    block = usage.get("rate_limit_reset_credits") if isinstance(usage, dict) else None
    if not isinstance(block, dict) or count(block.get("available_count")) == 0:
        return raw
    try:
        details = json.loads(request(RESET_CREDITS_URL, headers, timeout=5))
        credits = details.get("credits") if isinstance(details, dict) else None
        if isinstance(credits, list):
            projected = []
            for item in credits:
                if not isinstance(item, dict):
                    continue
                display = {key: item.get(key) for key in ("status", "title", "expires_at")}
                credit_id = item.get("id")
                account_id = headers.get("ChatGPT-Account-Id")
                if (isinstance(account_id, str) and account_id.strip()
                        and item.get("reset_type") == "codex_rate_limits" and isinstance(credit_id, str) and credit_id):
                    display["action_id"] = hashlib.sha256(credit_id.encode("utf-8")).hexdigest()
                projected.append(display)
            block["credits"] = projected
    except (QueryError, ValueError):
        # Expiries are optional; a failed detail query must not hide usage/count.
        pass
    return json.dumps(usage)


def main():
    output(query)


if __name__ == "__main__":
    main()
