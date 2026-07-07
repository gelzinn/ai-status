import json

def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"provider": "Z.AI", "metrics": []}

    if not data.get("success"):
        return {"provider": "Z.AI", "metrics": []}

    level = data.get("data", {}).get("level", "")
    limits = data.get("data", {}).get("limits", [])

    provider = f"Z.AI Coding Plan ({level.upper()})" if level else "Z.AI Coding Plan"

    metrics = []
    for limit in limits:
        t = limit.get("type", "")
        unit = limit.get("unit", "")
        pct = limit.get("percentage", 0)
        reset_ts = limit.get("nextResetTime", 0)

        reset_secs = None
        if reset_ts:
            secs = (reset_ts / 1000) - __import__('time').time()
            if secs > 0:
                reset_secs = round(secs)

        if t == "TOKENS_LIMIT" and unit == 3:
            metric_type = "rolling"
        elif t == "TOKENS_LIMIT" and unit == 6:
            metric_type = "weekly"
        elif t == "TIME_LIMIT" or (t == "TOKENS_LIMIT" and unit == 5):
            metric_type = "monthly"
        else:
            metric_type = "generic"

        metrics.append({
            "type": metric_type,
            "percentage": pct,
            "reset_in_seconds": reset_secs
        })

    return {"provider": provider, "metrics": metrics}
