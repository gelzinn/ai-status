"""Organization month costs; requires an OpenAI organization Admin API key."""
import os

from core.metered import iso_time, month_window, options, paginated
from core.provider_http import QueryError, output, require_token


def query():
    token = require_token(os.environ.get("OPENAI_ADMIN_KEY"),
                          "Set OPENAI_ADMIN_KEY to an organization Admin API key; regular project keys cannot read organization costs.")
    opts = options()
    start, now, end = month_window()
    headers = {"Authorization": f"Bearer {token}"}
    organization = opts.get("organization_id") or os.environ.get("OPENAI_ORG_ID")
    if organization:
        headers["OpenAI-Organization"] = str(organization)
    params = {"start_time": int(start.timestamp()), "end_time": int(now.timestamp()),
              "bucket_width": "1d", "limit": 31}
    projects = opts.get("project_ids") or ([opts["project_id"]] if opts.get("project_id") else None)
    if projects:
        params["project_ids[]"] = projects
    if opts.get("api_key_ids"):
        params["api_key_ids[]"] = opts["api_key_ids"]
    try:
        buckets = paginated("https://api.openai.com/v1/organization/costs", headers, params)
    except QueryError as exc:
        if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
            raise QueryError("OpenAI cost access denied; use an organization Admin API key with cost-reading permission (OPENAI_ADMIN_KEY).") from None
        raise
    return {"data": buckets, "_ai_status": {"reset_at": iso_time(end),
            "monthly_budget": opts.get("monthly_budget"), "budget_currency": opts.get("budget_currency", "USD")}}


def main():
    output(query)


if __name__ == "__main__":
    main()
