"""Read-only reset inventories shared by the native panel and Waybar tooltip."""

from datetime import datetime, timezone


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except ValueError:
        return None


def _credit(title, expiry, count=1):
    title = title.strip() if isinstance(title, str) else ""
    title = title if title and len(title) <= 200 and title.isprintable() else ""
    date = _date(expiry)
    return {
        "title": title,
        "count": count,
        "expires_at": date.astimezone(timezone.utc).isoformat() if date else None,
    }


def from_claude(usage):
    block = usage.get("cedar_ember")
    if not isinstance(block, dict) or block.get("eligible") is not True:
        return None
    credits = []
    grants = block.get("grants")
    for grant in grants if isinstance(grants, list) else []:
        if not isinstance(grant, dict):
            continue
        count = _count(grant.get("resets_left"))
        if not count or grant.get("usable_now") is not True or grant.get("paused", False) is not False:
            continue
        credit = _credit(grant.get("label"), grant.get("ends_at"), count)
        credits.append(credit)
    return {"available": sum(credit["count"] for credit in credits), "credits": credits}


def from_codex(usage):
    block = usage.get("rate_limit_reset_credits")
    if not isinstance(block, dict):
        return None
    count = _count(block.get("available_count"))
    if count is None:
        return None
    entries = block.get("credits")
    credits = [
        _credit(entry.get("title"), entry.get("expires_at"))
        for entry in entries if isinstance(entry, dict) and entry.get("status") == "available"
    ] if isinstance(entries, list) else []
    # The count from the usage response remains authoritative across a redemption.
    return {"available": count, "credits": credits[:count]}


def presentation(inventory, now=None):
    """Expose only display fields; never forward redemption handles or tokens."""
    if not isinstance(inventory, dict) or not _count(inventory.get("available")):
        return None
    now = now or datetime.now(timezone.utc)
    available = inventory["available"]
    lines = []
    entries = inventory.get("credits")
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        credit = _credit(entry.get("title"), entry.get("expires_at"), _count(entry.get("count")) or 1)
        date = _date(credit["expires_at"])
        if date:
            local = date.astimezone().strftime("%b %d %H:%M %Z")
            remaining = int((date - now).total_seconds())
            if remaining <= 0:
                detail = "Expired " + local
            else:
                days, remainder = divmod(remaining, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes = remainder // 60
                countdown = f"{days}d {hours}h" if days else f"{hours}h {minutes}m" if hours else f"{minutes}m"
                detail = f"Expires {local} (in {countdown})"
        else:
            detail = "Expiration not reported"
        title = credit["title"] or "Reset credit"
        if credit["count"] > 1:
            title += f" ×{credit['count']}"
        lines.append(f"{title} · {detail}")
    if not lines:
        lines.append("Expiration not reported")
    return {
        "available": available,
        "summary": f"{available} reset{'s' if available != 1 else ''} available",
        "details": lines,
    }
