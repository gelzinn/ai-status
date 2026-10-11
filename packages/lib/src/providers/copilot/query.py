from core.paths import opencode_file, read_json
import os
import shutil
from core.provider_http import QueryError, output, request, require_token, run_cli


def query():
    explicit = bool(os.environ.get("AI_STATUS_ACCOUNT_ID"))
    token = os.environ.get("GITHUB_COPILOT_TOKEN")
    if not token and (not explicit or os.environ.get("AI_STATUS_AUTH_FILE")):
        token = (read_json(os.environ.get("AI_STATUS_AUTH_FILE") or opencode_file("auth.json")).get("github-copilot") or {}).get("access")
    if not token and shutil.which("gh") and (not explicit or os.environ.get("GH_CONFIG_DIR")):
        try:
            token = run_cli(["gh", "auth", "token"]).strip()
        except QueryError:
            pass
    require_token(token, "Sign in with gh auth login, connect Copilot in OpenCode, or set GITHUB_COPILOT_TOKEN.")
    return request("https://api.github.com/copilot_internal/user", {
        "Authorization": f"token {token}", "Accept": "application/json",
        "Editor-Version": "vscode/1.96.2",
    })


def main():
    output(query)


if __name__ == "__main__":
    main()
