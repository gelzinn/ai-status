import json
import os
from pathlib import Path
import time
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token

# This read-only block is gated on the Claude CLI surface and version.
USAGE_URL = "https://api.anthropic.com/api/oauth/usage?cedar_ember=1"
USAGE_USER_AGENT = "claude-cli/2.1.281 (external, cli)"


def query():
    explicit = bool(os.environ.get("AI_STATUS_ACCOUNT_ID"))
    if explicit and not os.environ.get("AI_STATUS_AUTH_FILE") and not os.environ.get("CLAUDE_CONFIG_DIR") and not os.environ.get("CLAUDE_ACCESS_TOKEN"):
        require_token(None, "Set auth_file, CLAUDE_CONFIG_DIR or CLAUDE_ACCESS_TOKEN for this Claude account.")
    direct = os.environ.get("CLAUDE_ACCESS_TOKEN")
    use_file = not direct or os.environ.get("AI_STATUS_AUTH_FILE") or os.environ.get("CLAUDE_CONFIG_DIR")
    creds = {}
    if use_file:
        path = os.environ.get("AI_STATUS_AUTH_FILE")
        if not path:
            configured_root = os.environ.get("CLAUDE_CONFIG_DIR")
            root = Path(configured_root) if configured_root else Path.home() / ".claude"
            path = root / ".credentials.json"
        creds = read_json(path).get("claudeAiOauth") or {}
    token = direct or creds.get("accessToken")
    expiry = creds.get("expiresAt") or 0
    try:
        expired = float(expiry) > 0 and float(expiry) <= time.time() * 1000
    except (TypeError, ValueError):
        expired = True
    plan = creds.get("subscriptionType") or ""
    if expired and not os.environ.get("CLAUDE_ACCESS_TOKEN") and explicit:
        require_token(None, "This Claude session expired; sign in again using its own CLI configuration.")
    if (not token or expired) and not explicit:
        auth = read_json(opencode_file("auth.json"))
        token = (auth.get("anthropic") or auth.get("claude") or {}).get("access")
        plan = ""
    require_token(token, "Sign in to Claude Code or connect Claude in OpenCode.")
    usage = json.loads(request(USAGE_URL, {
        "Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20",
        "User-Agent": USAGE_USER_AGENT,
    }, timeout=15))
    return {"plan": plan, "usage": usage}


def main():
    output(query)


if __name__ == "__main__":
    main()
