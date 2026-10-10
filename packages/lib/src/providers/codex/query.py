import json
import os
from pathlib import Path
from core.paths import read_json
from core.provider_http import QueryError, output, request, require_token
from core.reset_credits import count

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def query():
    if os.environ.get("AI_STATUS_ACCOUNT_ID") and not any(os.environ.get(key) for key in ("AI_STATUS_AUTH_FILE", "CODEX_HOME", "CODEX_ACCESS_TOKEN")):
        raise QueryError("Set auth_file, CODEX_HOME or CODEX_ACCESS_TOKEN for this Codex account.")
    direct = os.environ.get("CODEX_ACCESS_TOKEN")
    use_file = not direct or os.environ.get("AI_STATUS_AUTH_FILE") or os.environ.get("CODEX_HOME")
    tokens = {}
    if use_file:
        path = os.environ.get("AI_STATUS_AUTH_FILE")
        if not path:
            configured_root = os.environ.get("CODEX_HOME")
            root = Path(configured_root) if configured_root else Path.home() / ".codex"
            path = root / "auth.json"
        tokens = read_json(path).get("tokens") or {}
    token = require_token(os.environ.get("CODEX_ACCESS_TOKEN") or tokens.get("access_token"), "Sign in to Codex with your ChatGPT account.")
    headers = {"Authorization": f"Bearer {token}"}
    account_id = os.environ.get("CODEX_ACCOUNT_ID") or tokens.get("account_id")
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id
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
            block["credits"] = [{key: item.get(key) for key in ("status", "title", "expires_at")}
                                for item in credits if isinstance(item, dict)]
    except (QueryError, ValueError):
        # Expiries are optional; a failed detail query must not hide usage/count.
        pass
    return json.dumps(usage)


def main():
    output(query)


if __name__ == "__main__":
    main()
