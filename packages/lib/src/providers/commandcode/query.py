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
from core.metered import number
from core.provider_http import QueryError, output, request, require_token

AUTH_FILE = os.path.expanduser("~/.commandcode/auth.json")
BASE_URL = os.environ.get("COMMANDCODE_API_URL", "https://api.commandcode.ai")
TIMEOUT = 8


def _api_key():
    key = os.environ.get("COMMANDCODE_API_KEY")
    if key:
        return key
    if os.environ.get("AI_STATUS_ACCOUNT_ID") and not os.environ.get("AI_STATUS_AUTH_FILE"):
        return None
    try:
        with open(os.environ.get("AI_STATUS_AUTH_FILE") or AUTH_FILE, encoding="utf-8-sig") as f:
            return json.load(f).get("apiKey")
    except (OSError, ValueError):
        return None


def _get(path, token):
    try:
        value = json.loads(request(f"{BASE_URL}{path}", {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ai-status",
        }, timeout=TIMEOUT))
    except (ValueError, TypeError):
        raise QueryError("Command Code returned an invalid billing response.") from None
    if not isinstance(value, dict) or "error" in value or "errors" in value:
        raise QueryError("Command Code returned no compatible billing data; check authentication.")
    return value


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

    credit_data = _get(f"/alpha/billing/credits{_q(org_id)}", token) or {}
    credits = credit_data.get("credits") or {}
    if not isinstance(credits, dict):
        raise QueryError("Command Code returned an invalid credit ledger.")
    balances = [number(credits[field]) for field in ("monthlyCredits", "purchasedCredits", "freeCredits") if field in credits]
    if any(value is None for value in balances):
        raise QueryError("Command Code returned an invalid credit amount.")
    remaining = sum(balances) if balances else None

    summary = _get(f"/alpha/usage/summary{_q(org_id, since)}", token) or {}
    used = number(summary.get("totalCost"))
    if "totalCost" in summary and (used is None or used < 0):
        raise QueryError("Command Code returned an invalid spend amount.")
    windows = credit_data.get("windowLimits") or credits.get("windowLimits") or {}
    if used is None and remaining is None and not windows:
        raise QueryError("Command Code returned no compatible billing metrics.")

    return {
        "used": used,
        "remaining": remaining,
        "tokens": summary.get("totalTokens"),
        "runs": summary.get("totalCount"),
        "period_end": period_end,
        "user": user_name,
        "windows": windows,
    }


def main():
    output(query)


if __name__ == "__main__":
    main()
