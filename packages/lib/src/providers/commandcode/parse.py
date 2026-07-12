import json
from datetime import datetime, timezone


def _reset_seconds(period_end):
    """Seconds until the current billing period ends, or None."""
    if not period_end:
        return None
    try:
        end = datetime.fromisoformat(str(period_end).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = (end - datetime.now(timezone.utc)).total_seconds()
        return int(delta) if delta > 0 else None
    except (ValueError, TypeError):
        return None


def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"provider": "Command Code", "metrics": []}

    used = float(data.get("used") or 0)
    remaining = float(data.get("remaining") or 0)
    total = used + remaining
    # Mirrors the CLI/dashboard: percent = spend / (spend + remaining credits).
    percentage = round(used / total * 100) if total > 0 else 0

    # Show the real spend truncated to the cent (never rounded up, so it never
    # overstates usage). The API exposes no plan-limit field; used + remaining is
    # the real budget (~$9.955), which the dashboard shows as the nominal plan
    # amount ($10) — so only the budget is rounded to a whole dollar.
    used_display = int(used * 100) / 100
    metric = {
        "type": "monthly",
        "percentage": percentage,
        "reset_in_seconds": _reset_seconds(data.get("period_end")),
        "detail": f"${used_display:.2f} of ${total:.0f} used",
    }

    return {"provider": "Command Code", "metrics": [metric]}
