import json

def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"provider": "GitHub Copilot", "metrics": []}

    snapshots = data.get("quota_snapshots", {})
    metrics = []

    for key, label in [("chat", "Chat"), ("completions", "Completions")]:
        quota = snapshots.get(key, {})
        limit = quota.get("limit", 0)
        remaining = quota.get("remaining", 0)
        pct = round((1 - remaining / limit) * 100) if limit > 0 else 0
        metrics.append({
            "name": label,
            "percentage": pct,
            "detail": f"{remaining}/{limit} remaining"
        })

    return {"provider": "GitHub Copilot", "metrics": metrics}
