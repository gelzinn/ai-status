import json
from datetime import datetime, timezone

GROUP_TYPES = {
    "session": "rolling",
    "daily": "daily",
    "weekly": "weekly",
    "monthly": "monthly",
}

PLAN_NAMES = {
    "max": "Max",
    "pro": "Pro",
    "team": "Team",
    "enterprise": "Enterprise",
}


def _seconds_until(iso_ts):
    if not iso_ts:
        return None
    try:
        resets_at = datetime.fromisoformat(iso_ts)
    except (ValueError, TypeError):
        return None
    if resets_at.tzinfo is None:
        resets_at = resets_at.replace(tzinfo=timezone.utc)
    secs = (resets_at - datetime.now(timezone.utc)).total_seconds()
    return round(secs) if secs > 0 else None


def _format_reset(seconds):
    if seconds is None:
        return None
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days > 0:
        return f"Resets in {days}d {hours}h"
    if hours > 0:
        return f"Resets in {hours}h {minutes}m"
    return f"Resets in {minutes}m"


def _scope_label(limit):
    scope = limit.get("scope") or {}
    model = scope.get("model") or {}
    return model.get("display_name") or scope.get("surface")


def _metrics_from_limits(limits):
    metrics = []
    for limit in limits:
        pct = limit.get("percent")
        if pct is None:
            continue
        mtype = GROUP_TYPES.get(limit.get("group"), "generic")
        reset_secs = _seconds_until(limit.get("resets_at"))
        metric = {
            "type": mtype,
            "percentage": round(float(pct)),
            "reset_in_seconds": reset_secs,
        }
        label = _scope_label(limit)
        if label:
            reset_text = _format_reset(reset_secs)
            metric["detail"] = f"{label} · {reset_text}" if reset_text else label
        metrics.append(metric)
    return metrics


def _metrics_from_windows(usage):
    metrics = []
    for key, mtype in (("five_hour", "rolling"), ("seven_day", "weekly")):
        window = usage.get(key)
        if not isinstance(window, dict) or window.get("utilization") is None:
            continue
        metrics.append({
            "type": mtype,
            "percentage": round(float(window["utilization"])),
            "reset_in_seconds": _seconds_until(window.get("resets_at")),
        })
    return metrics


def parse(raw_output):
    if raw_output == "NO_TOKEN":
        return {"provider": "Claude", "metrics": []}

    if raw_output == "OFFLINE" or not raw_output.startswith("{"):
        return {
            "provider": "Claude",
            "metrics": [{"type": "generic", "percentage": 0, "detail": "API unreachable"}],
        }

    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"provider": "Claude", "metrics": []}

    plan = data.get("plan") or ""
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else data

    provider = "Claude"
    plan_name = PLAN_NAMES.get(plan.lower()) if plan else None
    if plan_name:
        provider = f"Claude ({plan_name})"

    if usage.get("type") == "error":
        message = (usage.get("error") or {}).get("message", "Authentication failed")
        return {
            "provider": provider,
            "metrics": [{"type": "generic", "percentage": 0, "detail": message}],
        }

    if "error" in usage:
        err = usage["error"]
        return {
            "provider": provider,
            "metrics": [{"type": "generic", "percentage": 0, "detail": err.get("message", "API error")}],
        }

    limits = usage.get("limits")
    metrics = _metrics_from_limits(limits) if isinstance(limits, list) else []
    if not metrics:
        metrics = _metrics_from_windows(usage)

    return {"provider": provider, "metrics": metrics}
