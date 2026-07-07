import json
import re
from datetime import datetime, timezone

def parse(raw_output):
    if not raw_output:
        return {"provider": "Kiro", "metrics": []}

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
