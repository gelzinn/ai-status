import os
from pathlib import Path
from core.paths import read_json
from core.provider_http import output, request, require_token


def query():
    root = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    tokens = read_json(root / "auth.json").get("tokens") or {}
    token = require_token(tokens.get("access_token"), "Sign in to Codex with your ChatGPT account.")
    headers = {"Authorization": f"Bearer {token}"}
    if tokens.get("account_id"):
        headers["ChatGPT-Account-Id"] = tokens["account_id"]
    return request("https://chatgpt.com/backend-api/wham/usage", headers, timeout=10)


def main():
    output(query)


if __name__ == "__main__":
    main()
