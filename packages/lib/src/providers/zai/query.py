from core.paths import opencode_file, read_json
from core.provider_http import output, request, require_token


def query():
    accounts = read_json(opencode_file("account.json")).get("accounts") or []
    token = next(((a.get("credential") or {}).get("key") for a in accounts
                  if a.get("serviceID") in ("zai", "zai-coding-plan")), None)
    require_token(token, "Connect Z.AI in OpenCode (account.json).")
    return request("https://api.z.ai/api/monitor/usage/quota/limit", {
        "Authorization": f"Bearer {token}", "Accept": "application/json",
    })


def main():
    output(query)


if __name__ == "__main__":
    main()
