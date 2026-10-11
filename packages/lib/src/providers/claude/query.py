import json
import os
from pathlib import Path
import time
import sys
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token

# This read-only block is gated on the Claude CLI surface and version.
USAGE_URL = "https://api.anthropic.com/api/oauth/usage?cedar_ember=1"
USAGE_USER_AGENT = "claude-cli/2.1.281 (external, cli)"


def query():
    explicit = bool(os.environ.get("AI_STATUS_ACCOUNT_ID"))
    auth_file = os.environ.get("AI_STATUS_AUTH_FILE")
    configured_root = os.environ.get("CLAUDE_CONFIG_DIR")
    direct = os.environ.get("CLAUDE_ACCESS_TOKEN")
    if explicit and not auth_file and not configured_root and not direct:
        require_token(None, "Set auth_file, CLAUDE_CONFIG_DIR or CLAUDE_ACCESS_TOKEN for this Claude account.")
    creds = {}
    if not direct or auth_file or configured_root:
        if auth_file:
            creds = read_json(auth_file).get("claudeAiOauth") or {}
        elif sys.platform == "darwin" and not direct:
            prepared = os.environ.get("AI_STATUS_CLAUDE_CREDENTIALS")
            if prepared is not None:
                # The parent fingerprinted this exact Keychain/file snapshot.
                # Reading again could bind a rotated login to the old cache.
                try:
                    creds = json.loads(prepared)
                except (TypeError, ValueError):
                    require_token(None, "Claude credentials could not be read; refresh and try again.")
                if not isinstance(creds, dict):
                    require_token(None, "Claude credentials could not be read; refresh and try again.")
            else:
                from core.macos_credentials import claude_credentials
                root = Path(configured_root) if configured_root else Path.home() / ".claude"
                creds = claude_credentials(root, scoped=bool(configured_root))
        else:
            root = Path(configured_root) if configured_root else Path.home() / ".claude"
            creds = read_json(root / ".credentials.json").get("claudeAiOauth") or {}
    token = direct or creds.get("accessToken")
    expiry = 0 if direct else creds.get("expiresAt") or 0
    try:
        expired = float(expiry) > 0 and float(expiry) <= time.time() * 1000
    except (TypeError, ValueError):
        expired = True
    plan = creds.get("subscriptionType") or ""
    if expired and explicit:
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
