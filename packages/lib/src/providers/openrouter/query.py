import os

from core.metered import json_request, options
from core.provider_http import output, require_token


def query():
    opts = options()
    management = os.environ.get("OPENROUTER_MANAGEMENT_KEY")
    token = require_token(os.environ.get("OPENROUTER_API_KEY") or management,
                          "Set OPENROUTER_API_KEY to read this key's usage; set OPENROUTER_MANAGEMENT_KEY for the account credit balance.")
    key = json_request("https://openrouter.ai/api/v1/key", {"Authorization": f"Bearer {token}"})
    result = {"key": key}
    if management or opts.get("include_credits") or ((key.get("data") or {}).get("is_management_key")):
        require_token(management or (token if (key.get("data") or {}).get("is_management_key") else None),
                      "OpenRouter account credits require OPENROUTER_MANAGEMENT_KEY; regular inference keys can only read their own usage.")
        result["credits"] = json_request("https://openrouter.ai/api/v1/credits", {"Authorization": f"Bearer {management or token}"})
    return result


def main():
    output(query)


if __name__ == "__main__":
    main()
