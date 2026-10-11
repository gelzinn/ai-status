import json
from datetime import datetime, timezone
from core.metered import amount_metric, number


def _reset_seconds(period_end):
    """Seconds until the current billing period ends, or None."""
    if not period_end:
        return None
    try:
        if isinstance(period_end, (int, float)):
            end = datetime.fromtimestamp(period_end / 1000, tz=timezone.utc)
        else:
            end = datetime.fromisoformat(str(period_end).replace("Z", "+00:00"))
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        delta = (end - datetime.now(timezone.utc)).total_seconds()
        return int(delta) if delta > 0 else None
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (ValueError, TypeError):
        data = None
    if not isinstance(data, dict) or "error" in data or "errors" in data:
        return {"provider": "Command Code", "metrics": [], "_error": "Command Code returned no compatible billing data."}

    used = number(data.get("used"))
    remaining = number(data.get("remaining"))
    metrics = []
    windows = data.get("windows") or {}
    for key, kind, label in (("fiveHour", "rolling", "5-hour spend"), ("weekly", "weekly", "Weekly spend")):
        window = windows.get(key) if isinstance(windows, dict) else None
        if not isinstance(window, dict):
            continue
        spend, cap = number(window.get("used")), number(window.get("cap"))
        if spend is None or spend < 0 or cap is None or cap <= 0:
            continue
        metrics.append(amount_metric(spend, "USD", f"{label}: ${spend:.2f} of ${cap:.2f} used", kind,
                                     cap, _reset_seconds(window.get("resetAt"))))
    # Spend + all remaining pools is not a provider-enforced monthly limit:
    # purchased and free credits can change that sum. Keep these amounts honest.
    if used is not None and used >= 0:
        metrics.append(amount_metric(used, "USD", "Monthly spend", "monthly", reset_in_seconds=_reset_seconds(data.get("period_end"))))
    if remaining is not None:
        metrics.append(amount_metric(remaining, "USD", "Available credits", "balance"))
    return {"provider": "Command Code", "metrics": metrics, **({"_error": "Command Code returned no compatible billing metrics."} if not metrics else {})}
