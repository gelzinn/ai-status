import json

def parse(raw_output):
    try:
        data = json.loads(raw_output)
    except (json.JSONDecodeError, ValueError):
        return {"provider": "Codex", "metrics": []}

    plan = data.get("plan_type", "free")
    used = data.get("rate_limit", {}).get("primary_window", {}).get("used_percent", 0)
    reset = data.get("rate_limit", {}).get("primary_window", {}).get("reset_after_seconds", None)

    return {
        "provider": f"Codex ({plan.capitalize()})",
        "metrics": [{
            "type": "generic",
            "percentage": int(used),
            "reset_in_seconds": int(reset) if reset else None
        }]
    }
