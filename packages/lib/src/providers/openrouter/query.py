import os

from core.metered import json_request, options
from core.provider_http import output, require_token


def query():
    options()
    management = os.environ.get("OPENROUTER_MANAGEMENT_KEY")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    token = require_token(api_key or management,
                          "Set OPENROUTER_API_KEY to read this key's usage; set OPENROUTER_MANAGEMENT_KEY for the account credit balance.")
    result = {}
    if api_key:
        key = json_request("https://openrouter.ai/api/v1/key", {"Authorization": f"Bearer {token}"})
        result["key"] = key
        data = key.get("data")
        if isinstance(data, dict) and data.get("is_management_key") is True:
            management = management or token
    if management:
        result["credits"] = json_request("https://openrouter.ai/api/v1/credits", {"Authorization": f"Bearer {management}"})
    else:
        # A regular inference key cannot read the account-wide credit endpoint.
        # Keep its valid usage even when include_credits was requested.
        result["_ai_status"] = {"credits_hint": "Set OPENROUTER_MANAGEMENT_KEY to track account credits."}
    return result


def main():
    output(query)


if __name__ == "__main__":
    main()
