import json
import os
from pathlib import Path
import time
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    root = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    creds = read_json(root / ".credentials.json").get("claudeAiOauth") or {}
    token = creds.get("accessToken")
    expiry = creds.get("expiresAt") or 0
    try:
        expired = float(expiry) > 0 and float(expiry) <= time.time() * 1000
    except (TypeError, ValueError):
        expired = True
    plan = creds.get("subscriptionType") or ""
    if not token or expired:
        auth = read_json(opencode_file("auth.json"))
        token = (auth.get("anthropic") or auth.get("claude") or {}).get("access")
        plan = ""
    require_token(token, "Sign in to Claude Code or connect Claude in OpenCode.")
    usage = json.loads(request("https://api.anthropic.com/api/oauth/usage", {
        "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20",
    }, timeout=15))
    return {"plan": plan, "usage": usage}


def main():
    output(query)


if __name__ == "__main__":
    main()
