import os
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    if os.environ.get("AI_STATUS_ACCOUNT_ID") and not os.environ.get("AI_STATUS_AUTH_FILE") and not os.environ.get("OPENCODE_GO_API_KEY"):
        require_token(None, "Set OPENCODE_GO_API_KEY or auth_file for this OpenCode Go account.")
    token = require_token(os.environ.get("OPENCODE_GO_API_KEY") or (read_json(os.environ.get("AI_STATUS_AUTH_FILE") or opencode_file("auth.json")).get("opencode-go") or {}).get("key"),
                          "Connect OpenCode Go in OpenCode.")
    return request("https://opencode.ai/zen/go/v1/usage", {"Authorization": f"Bearer {token}"})


def main():
    output(query)


if __name__ == "__main__":
    main()
