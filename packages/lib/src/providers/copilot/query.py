from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    token = require_token((read_json(opencode_file("auth.json")).get("github-copilot") or {}).get("access"),
                          "Connect GitHub Copilot in OpenCode.")
    return request("https://api.github.com/copilot_internal/user", {
        "Authorization": f"token {token}", "Accept": "application/json",
        "Editor-Version": "vscode/1.96.2",
    })


def main():
    output(query)


if __name__ == "__main__":
    main()
