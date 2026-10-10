import json
import os
from pathlib import Path
from core.paths import read_json
from core.provider_http import QueryError, output, request, require_token
from core.reset_credits import count

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"


def query():
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    tokens = read_json(root / "auth.json").get("tokens") or {}
    token = require_token(tokens.get("access_token"), "Sign in to Codex with your ChatGPT account.")
    headers = {"Authorization": f"Bearer {token}"}
    if tokens.get("account_id"):
        headers["ChatGPT-Account-Id"] = tokens["account_id"]
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
