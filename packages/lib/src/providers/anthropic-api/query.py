"""Claude Console costs, not Claude subscriptions or Bedrock/Vertex invoices."""
import os

from core.metered import iso_time, month_window, options, paginated
from core.provider_http import QueryError, output, require_token


def query():
    oauth = os.environ.get("ANTHROPIC_ADMIN_TOKEN")
    token = require_token(oauth or os.environ.get("ANTHROPIC_ADMIN_KEY"),
                          "Set ANTHROPIC_ADMIN_KEY to a Claude Console Admin API key or an unscoped personal/service account key with admin access, or ANTHROPIC_ADMIN_TOKEN to an org:admin OAuth token; workspace keys cannot read costs.")
    opts = options()
    start, now, end = month_window()
    headers = {"anthropic-version": "2023-06-01", **({"Authorization": f"Bearer {token}"} if oauth else {"x-api-key": token})}
    params = {"starting_at": iso_time(start), "ending_at": iso_time(now), "bucket_width": "1d", "limit": 31}
    # Cost reporting only exposes workspace grouping, not a workspace filter.
    # Filter grouped costs locally after collecting every page.
    if opts.get("workspace_id"):
        params["group_by[]"] = ["workspace_id"]
    try:
        buckets = paginated("https://api.anthropic.com/v1/organizations/cost_report", headers, params)
    except QueryError as exc:
        if "HTTP 401" in str(exc) or "HTTP 403" in str(exc):
            raise QueryError("Anthropic API cost access denied; use a Console Admin API credential (ANTHROPIC_ADMIN_KEY), or an org:admin OAuth token (ANTHROPIC_ADMIN_TOKEN); workspace inference keys cannot read costs.") from None
        raise
    return {"data": buckets, "_ai_status": {"reset_at": iso_time(end), "workspace_id": opts.get("workspace_id"),
            "monthly_budget": opts.get("monthly_budget"), "budget_currency": opts.get("budget_currency", "USD")}}


def main():
    output(query)


if __name__ == "__main__":
    main()
