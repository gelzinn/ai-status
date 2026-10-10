import os
from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    explicit = bool(os.environ.get("AI_STATUS_ACCOUNT_ID"))
    accounts = read_json(os.environ.get("AI_STATUS_AUTH_FILE") or opencode_file("account.json")).get("accounts") or []
    token = os.environ.get("ZAI_API_KEY") or (next(((a.get("credential") or {}).get("key") for a in accounts
                  if a.get("serviceID") in ("zai", "zai-coding-plan")), None)
                  if not explicit or os.environ.get("AI_STATUS_AUTH_FILE") else None)
    require_token(token, "Set ZAI_API_KEY or connect Z.AI in OpenCode (account.json).")
    return request("https://api.z.ai/api/monitor/usage/quota/limit", {
        "Authorization": f"Bearer {token}", "Accept": "application/json",
    })


def main():
    output(query)


if __name__ == "__main__":
    main()
