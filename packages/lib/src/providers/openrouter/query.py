import os

from core.metered import json_request, options
from core.provider_http import QueryError, output, require_token


def query():
    options()
    management = os.environ.get("OPENROUTER_MANAGEMENT_KEY")
    api_key = os.environ.get("OPENROUTER_API_KEY")
    token = require_token(api_key or management,
                          "Set OPENROUTER_API_KEY (or OPENROUTER_MANAGEMENT_KEY) to read OpenRouter usage and credits.")
    result = {}
    if api_key:
        key = json_request("https://openrouter.ai/api/v1/key", {"Authorization": f"Bearer {token}"})
        result["key"] = key
    try:
        # Try the configured key regardless of its is_management_key flag.
        # An explicit management key remains an optional account override.
        result["credits"] = json_request("https://openrouter.ai/api/v1/credits", {"Authorization": f"Bearer {management or token}"})
    except QueryError as error:
        if management or error.status not in (401, 403):
            raise
        # /key succeeded, but this key cannot read account-wide credits.
        # Retain its usage without exposing server messages or credentials.
        result["_ai_status"] = {"credits_hint": "Account balance unavailable for this key."}
    return result


def main():
    output(query)


if __name__ == "__main__":
    main()
