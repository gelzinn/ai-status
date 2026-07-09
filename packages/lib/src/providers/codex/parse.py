import json


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
    except (json.JSONDecodeError, ValueError):
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

    return {
        "provider": f"Codex ({plan.capitalize()})",
        "metrics": metrics,
    }
