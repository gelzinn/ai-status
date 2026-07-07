import json
import re

def parse(raw_output):
    if not raw_output:
        return []

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
