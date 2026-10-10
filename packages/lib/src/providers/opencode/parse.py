import html
import json
import re
from core.metered import number, reset_seconds as seconds_until_reset

def parse(raw_output):
    if not raw_output:
        return {"provider": "OpenCode (Go)", "metrics": []}

    try:
        data = json.loads(raw_output)
    except ValueError:
        data = None
    if isinstance(data, dict):
        metrics = []
        usage = data.get("usage") or {}
        if not isinstance(usage, dict) or data.get("error"):
            return {"provider": "OpenCode (Go)", "metrics": []}
        for kind in ("rolling", "weekly", "monthly"):
            window = usage.get(kind)
            if not isinstance(window, dict):
                continue
            pct = number(window.get("percent"))
            if pct is None or not 0 <= pct <= 100:
                continue
            metrics.append({"type": kind, "percentage": pct,
                            "reset_in_seconds": seconds_until_reset(window.get("resetsAt"))})
        return {"provider": "OpenCode (Go)", "metrics": metrics}

    text = html.unescape(raw_output).replace('\\"', '"')

    plan = "Go"
    provider = f"OpenCode ({plan})" if plan else "OpenCode Go"

    fields = {
        "rolling": "rollingUsage",
        "weekly": "weeklyUsage",
        "monthly": "monthlyUsage",
    }

    number_pattern = r'"?(-?\d+(?:\.\d+)?)"?'

    metrics = []
    for key, field in fields.items():
        object_match = re.search(rf'["\']?{re.escape(field)}["\']?\s*:\s*(?:\$R\[\d+\]\s*=\s*)?\{{(?P<body>[^{{}}]*)\}}', text, re.DOTALL)
        if not object_match:
            continue

        body = object_match.group("body")
        usage_match = re.search(rf'["\']?usagePercent["\']?\s*:\s*{number_pattern}', body)
        reset_match = re.search(rf'["\']?resetInSec["\']?\s*:\s*{number_pattern}', body)
        if not usage_match or not reset_match:
            continue

        usage_percent = float(usage_match.group(1))
        reset_seconds = int(float(reset_match.group(1)))

        metrics.append({
            "type": key,
            "percentage": usage_percent,
            "reset_in_seconds": reset_seconds if reset_seconds > 0 else None
        })

    if not metrics:
        return {"provider": "OpenCode (Go)", "metrics": []}

    return {"provider": provider, "metrics": metrics}
