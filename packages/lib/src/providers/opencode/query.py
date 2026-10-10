import os
from pathlib import Path
import urllib.parse
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    token = require_token((read_json(opencode_file("auth.json")).get("opencode-go") or {}).get("key"),
                          "Connect OpenCode Go in OpenCode.")
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    cfg = read_json(root / "opencode-bar/opencode-go.json")
    workspace = require_token(cfg.get("workspaceId"), "Set workspaceId and authCookie in opencode-go.json.")
    cookie = require_token(cfg.get("authCookie"), "Set workspaceId and authCookie in opencode-go.json.")
    request("https://opencode.ai/zen/go/v1/models", {"Authorization": f"Bearer {token}"})
    return request(f"https://opencode.ai/workspace/{urllib.parse.quote(workspace, safe='')}/go", {
        "Cookie": cookie, "Accept": "text/html,application/xhtml+xml",
    })


def main():
    output(query)


if __name__ == "__main__":
    main()
