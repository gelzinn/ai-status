import json
import re
from datetime import datetime, timezone
from core.metered import amount_metric, number


def parse_api(raw_output):
    try:
        data = json.loads(raw_output)
        rows = data.get("usageBreakdownList")
        if not isinstance(rows, list):
            raise ValueError
        credits = [row for row in rows if isinstance(row, dict) and row.get("resourceType") == "CREDIT"]
        if len(credits) == 1:
            row = credits[0]
        elif not credits and len(rows) == 1 and isinstance(rows[0], dict) and not rows[0].get("resourceType"):
            row = rows[0]
        else:
            raise ValueError
        used, limit = number(row.get("currentUsageWithPrecision")), number(row.get("usageLimitWithPrecision"))
        if used is None or limit is None or used < 0 or limit < 0:
            raise ValueError
        reset = number(data.get("nextDateReset"))
        if data.get("nextDateReset") is not None and (reset is None or reset < 0):
            raise ValueError
        reset = max(0, int(reset - datetime.now(timezone.utc).timestamp())) if reset else None
        plan = (data.get("subscriptionInfo") or {}).get("subscriptionTitle") or ""
        return {"provider": "Kiro", "plan": str(plan), "metrics": [
            amount_metric(used, "credits", "Monthly credits used", "monthly", limit, reset)
        ]}
    except (ValueError, TypeError, AttributeError, OverflowError):
        return {"provider": "Kiro", "metrics": [], "_error": "Kiro returned no compatible credit quota; check the session and response format."}

def parse(raw_output):
    if not raw_output:
        return {"provider": "Kiro", "metrics": []}
    if raw_output.lstrip().startswith("{"):
        return parse_api(raw_output)

    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_output)
    text = text.replace('\u00a0', ' ')

    credit_match = re.search(r'Credits\s*\(([0-9,.]+)\s+of\s+([0-9,.]+)', text)
    if not credit_match:
        return {"provider": "Kiro", "metrics": []}

    used = float(credit_match.group(1).replace(',', ''))
    total = float(credit_match.group(2).replace(',', ''))
    pct = round((used / total) * 100) if total > 0 else 0

    plan_match = re.search(r'KIRO\s+(\S+)', text, re.IGNORECASE)
    plan = plan_match.group(1).upper() if plan_match else ""
    provider = f"Kiro ({plan})" if plan else "Kiro"

    delta = None
    reset_match = re.search(r'resets on (\d{4}-\d{2}-\d{2})', text, re.IGNORECASE)
    if reset_match:
        reset_date = datetime.strptime(reset_match.group(1), '%Y-%m-%d').replace(tzinfo=timezone.utc)
        delta = int((reset_date - datetime.now(timezone.utc)).total_seconds())

    return {
        "provider": provider,
        "metrics": [{
            "type": "generic",
            "percentage": pct,
            "reset_in_seconds": delta if (delta and delta > 0) else None
        }]
    }
