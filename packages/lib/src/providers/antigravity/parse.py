import json
import re
from datetime import datetime, timezone
from core.metered import number


def parse_api(raw_output):
    try:
        data = json.loads(raw_output)
        response = data.get("response")
        groups = response.get("groups") if isinstance(response, dict) else None
        if not isinstance(groups, list):
            groups = data.get("groups")
        if not isinstance(groups, list):
            raise ValueError
        pools = {"Gemini": [], "Claude/GPT": []}
        seen = set()
        for group in groups:
            name = str(group.get("displayName") or "").lower()
            for bucket in group.get("buckets") or []:
                identity = str(bucket.get("bucketId") or "").lower()
                window = bucket.get("window")
                kind = ("weekly" if identity.endswith("weekly") or window == "weekly" else
                        "rolling" if identity.endswith("5h") or window == "5h" else None)
                pool = ("Gemini" if identity.startswith("gemini") else "Claude/GPT" if identity.startswith("3p") else
                        "Gemini" if "gemini" in name else "Claude/GPT" if "claude" in name or "gpt" in name else None)
                if kind is None or pool is None:
                    continue
                fraction = number(bucket.get("remainingFraction"))
                if fraction is None or not 0 <= fraction <= 1 or (pool, kind) in seen:
                    raise ValueError
                seen.add((pool, kind))
                reset = bucket.get("resetTime")
                if reset:
                    stamp = datetime.fromisoformat(str(reset).replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    reset = max(0, int((stamp - datetime.now(timezone.utc)).total_seconds()))
                pools[pool].append({"type": kind, "percentage": round((1-fraction)*100, 2),
                                    "detail": "Weekly quota" if kind == "weekly" else "5-hour quota",
                                    "reset_in_seconds": reset or None})
        if not seen:
            raise ValueError
        return [{"provider": pool + " (Antigravity)", "metrics": metrics} for pool, metrics in pools.items() if metrics]
    except (ValueError, TypeError, AttributeError, OverflowError):
        return [{"provider": "Antigravity", "metrics": [], "_error": "Antigravity returned no compatible quota windows; check the session and response format."}]

def parse(raw_output):
    if not raw_output:
        return []
    if raw_output.lstrip().startswith("{"):
        return parse_api(raw_output)

    providers = parse_agy_output(raw_output)
    return providers


def parse_time_to_seconds(time_str):
    days = 0
    hours = 0
    minutes = 0

    d_match = re.search(r'(\d+)d', time_str)
    if d_match:
        days = int(d_match.group(1))
    h_match = re.search(r'(\d+)h', time_str)
    if h_match:
        hours = int(h_match.group(1))
    m_match = re.search(r'(\d+)m', time_str)
    if m_match:
        minutes = int(m_match.group(1))

    if "hour" in time_str:
        h_match = re.search(r'(\d+)\s+hour', time_str)
        if h_match:
            hours = int(h_match.group(1))
    if "minute" in time_str:
        m_match = re.search(r'(\d+)\s+minute', time_str)
        if m_match:
            minutes = int(m_match.group(1))

    total = days * 86400 + hours * 3600 + minutes * 60
    return total if total > 0 else None


def parse_block(block_text, prefix):
    if not block_text:
        return None

    metrics = []

    weekly_match = re.search(
        r'Weekly Limit\s*\n\s*\[[^\]]*\]\s*([\d.]+)%\s*\n\s*([^\n]+)',
        block_text, re.IGNORECASE
    )
    if weekly_match:
        rem_pct = float(weekly_match.group(1))
        used_pct = round(100.0 - rem_pct)
        detail = weekly_match.group(2).strip()
        detail = re.sub(r'\s{2,}.*', '', detail)

        reset_secs = None
        if "Quota available" not in detail:
            reset_secs = parse_time_to_seconds(detail)

        metrics.append({
            "type": "weekly",
            "percentage": used_pct,
            "reset_in_seconds": reset_secs
        })

    five_hour_match = re.search(
        r'(?:Five Hour Limit|5-Hour Limit|5 Hour Limit)\s*\n\s*\[[^\]]*\]\s*([\d.]+)%\s*\n\s*([^\n]+)',
        block_text, re.IGNORECASE
    )
    if five_hour_match:
        rem_pct = float(five_hour_match.group(1))
        used_pct = round(100.0 - rem_pct)
        detail = five_hour_match.group(2).strip()
        detail = re.sub(r'\s{2,}.*', '', detail)

        reset_secs = None
        if "Quota available" not in detail:
            reset_secs = parse_time_to_seconds(detail)

        metrics.append({
            "type": "rolling",
            "percentage": used_pct,
            "reset_in_seconds": reset_secs
        })

    if metrics:
        return {"provider": f"{prefix} (Antigravity)", "metrics": metrics}
    return None


def parse_agy_output(text):
    start_idx = text.find("Models & Quota")
    if start_idx == -1:
        start_idx = text.find("GEMINI MODELS")
    if start_idx == -1:
        return []

    text_to_parse = text[start_idx:]

    gemini_block_match = re.search(r'GEMINI MODELS(.*?(?=(?:CLAUDE AND GPT MODELS|$)))', text_to_parse, re.DOTALL | re.IGNORECASE)
    claude_block_match = re.search(r'CLAUDE AND GPT MODELS(.*)', text_to_parse, re.DOTALL | re.IGNORECASE)

    providers = []
    if gemini_block_match:
        gemini_prov = parse_block(gemini_block_match.group(1), "Gemini")
        if gemini_prov:
            providers.append(gemini_prov)
    if claude_block_match:
        claude_prov = parse_block(claude_block_match.group(1), "Claude/GPT")
        if claude_prov:
            providers.append(claude_prov)

    return providers
