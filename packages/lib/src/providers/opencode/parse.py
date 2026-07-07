import html
import json
import re

def parse(raw_output):
    if not raw_output:
        return {"provider": "OpenCode (Go)", "metrics": []}

    text = html.unescape(raw_output).replace('\\"', '"')

    plan = "Go"
    provider = f"OpenCode ({plan})" if plan else "OpenCode Go"

    fields = {
        "rolling": "rollingUsage",
        "weekly": "weeklyUsage",
        "monthly": "monthlyUsage",
    }

    number = r'"?(-?\d+(?:\.\d+)?)"?'

    metrics = []
    for key, field in fields.items():
        object_match = re.search(rf'["\']?{re.escape(field)}["\']?\s*:\s*(?:\$R\[\d+\]\s*=\s*)?\{{(?P<body>[^{{}}]*)\}}', text, re.DOTALL)
        if not object_match:
            continue

        body = object_match.group("body")
        usage_match = re.search(rf'["\']?usagePercent["\']?\s*:\s*{number}', body)
        reset_match = re.search(rf'["\']?resetInSec["\']?\s*:\s*{number}', body)
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
