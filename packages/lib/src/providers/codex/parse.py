import json
from core.metered import amount_metric, number
from core.reset_credits import from_codex


def _usage_credits(data):
    """Usage credits are a balance, separate from quota windows and resets."""
    credits = data.get("credits")
    if not isinstance(credits, dict):
        return None
    if credits.get("unlimited") is True:
        return {"type": "credits", "name": "Usage credits (credits)",
                "percentage": None, "value": "Unlimited", "unit": "credits",
                "detail": "", "reset_in_seconds": None}
    balance = number(credits.get("balance"))
    if balance is not None:
        # A zero or negative balance is still provider-reported information.
        return amount_metric(balance, "credits", "Usage credits", "credits")
    if credits.get("has_credits") is True:
        return {"type": "credits", "name": "Usage credits (credits)",
                "percentage": None, "value": "Available", "unit": "credits",
                "detail": "Balance not reported", "reset_in_seconds": None}
    return None


def _window_type(seconds):
    """Classify a Codex rate-limit window by its length so it gets a meaningful
    label. Codex reports a short rolling window plus a weekly one on paid plans,
    and a single monthly window on free.
    """
    if not seconds:
        return "generic"
    hours = seconds / 3600
    if hours <= 6:
        return "rolling"       # e.g. the 5-hour window
    if hours <= 36:
        return "daily"
    if hours <= 24 * 10:
        return "weekly"        # ~7-day window
    return "monthly"           # ~30-day window (free plan)


def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (ValueError, TypeError):
        return {"provider": "Codex", "metrics": []}
    if not isinstance(data, dict):
        return {"provider": "Codex", "metrics": []}

    plan = data.get("plan_type", "free")
    rate_limit = data.get("rate_limit") or {}

    metrics = []
    # Codex exposes usage in up to two windows: primary (5h on paid, monthly on
    # free) and secondary (weekly on paid, absent otherwise).
    for key in ("primary_window", "secondary_window"):
        window = rate_limit.get(key)
        if not isinstance(window, dict):
            continue
        reset = window.get("reset_after_seconds")
        metrics.append({
            "type": _window_type(window.get("limit_window_seconds")),
            "percentage": int(window.get("used_percent", 0)),
            "reset_in_seconds": int(reset) if reset else None,
        })

    usage_credits = _usage_credits(data)
    if usage_credits is not None:
        metrics.append(usage_credits)

    result = {
        "provider": f"Codex ({plan.capitalize()})",
        "metrics": metrics,
    }
    credits = from_codex(data)
    if credits is not None:
        result["reset_credits"] = credits
    return result
