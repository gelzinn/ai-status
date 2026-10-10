#!/usr/bin/env python3
"""Query Command Code (commandcode.ai) monthly usage.

Reads the API key the `cmd` CLI stores in ~/.commandcode/auth.json (written on
`cmd login` as {"apiKey": ...}) — or the COMMANDCODE_API_KEY env var — and calls
the same public /alpha endpoints the CLI's own usage view uses:

  GET /alpha/whoami                          -> org id
  GET /alpha/billing/subscriptions?orgId=    -> current billing period
  GET /alpha/billing/credits?orgId=          -> remaining credit pool
  GET /alpha/usage/summary?orgId=&since=     -> spend / tokens / runs this period

Prints a small merged JSON blob for parse.py, or nothing (exit 0) when there is
no auth — matching the other CLI-backed providers.
"""
import json
import os
import urllib.parse
from core.provider_http import output, request, require_token

AUTH_FILE = os.path.expanduser("~/.commandcode/auth.json")
BASE_URL = os.environ.get("COMMANDCODE_API_URL", "https://api.commandcode.ai")
TIMEOUT = 8


def _api_key():
    key = os.environ.get("COMMANDCODE_API_KEY")
    if key:
        return key
    try:
        with open(AUTH_FILE, encoding="utf-8-sig") as f:
            return json.load(f).get("apiKey")
    except (OSError, ValueError):
        return None


def _get(path, token):
    return json.loads(request(f"{BASE_URL}{path}", {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ai-status",
    }, timeout=TIMEOUT))


def _q(org_id=None, since=None):
    params = {}
    if org_id:
        params["orgId"] = str(org_id)
    if since:
        params["since"] = str(since)
    return ("?" + urllib.parse.urlencode(params)) if params else ""


def query():
    token = require_token(_api_key(), "Sign in with cmd login or set COMMANDCODE_API_KEY.")

    whoami = _get("/alpha/whoami", token) or {}
    org_id = (whoami.get("org") or {}).get("id")
    user = whoami.get("user") or {}
    user_name = user.get("userName") or whoami.get("userName")

    sub_data = (_get(f"/alpha/billing/subscriptions{_q(org_id)}", token) or {}).get("data") or {}
    since = sub_data.get("currentPeriodStart")
    period_end = sub_data.get("currentPeriodEnd")

    credits = (_get(f"/alpha/billing/credits{_q(org_id)}", token) or {}).get("credits") or {}
    remaining = (
        max(0.0, float(credits.get("monthlyCredits") or 0))
        + max(0.0, float(credits.get("purchasedCredits") or 0))
        + max(0.0, float(credits.get("freeCredits") or 0))
    )

    summary = _get(f"/alpha/usage/summary{_q(org_id, since)}", token) or {}
    used = max(0.0, float(summary.get("totalCost") or 0))

    return {
        "used": used,
        "remaining": remaining,
        "tokens": summary.get("totalTokens"),
        "runs": summary.get("totalCount"),
        "period_end": period_end,
        "user": user_name,
    }


def main():
    output(query)


if __name__ == "__main__":
    main()
