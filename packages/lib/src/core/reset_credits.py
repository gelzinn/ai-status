"""Read-only reset-credit metadata shared by provider parsers and desktop/Waybar."""
from datetime import datetime, timezone


def count(value):
    if isinstance(value, float) and not value.is_integer():
        return 0
    try:
        return max(0, int(value)) if not isinstance(value, bool) else 0
    except (ValueError, TypeError, OverflowError):
        return 0


def expiry(value):
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date
    except ValueError:
        return None


def credit(title, amount, expires_at):
    # Redemption IDs are deliberately absent from the display/cache model.
    date = expiry(expires_at)
    return {"title": " ".join(title.split())[:240] if isinstance(title, str) else None,
            "count": amount, "expires_at": date.isoformat() if date else None}


def from_claude(usage):
    block = usage.get("cedar_ember")
    if not isinstance(block, dict):
        return None
    credits = []
    if block.get("eligible") is True:
        grants = block.get("grants")
        for grant in grants if isinstance(grants, list) else []:
            if not isinstance(grant, dict) or grant.get("usable_now") is not True or grant.get("paused"):
                continue
            amount = count(grant.get("resets_left"))
            if amount:
                credits.append(credit(grant.get("label"), amount, grant.get("ends_at")))
    return {"available": sum(item["count"] for item in credits), "credits": credits}


def from_codex(data):
    block = data.get("rate_limit_reset_credits")
    if not isinstance(block, dict):
        return None
    details = block.get("credits")
    credits = [credit(item.get("title"), 1, item.get("expires_at"))
               for item in details if isinstance(item, dict) and item.get("status") == "available"] if isinstance(details, list) else []
    return {"available": count(block.get("available_count")), "credits": credits}


def display_lines(block, now=None):
    if not isinstance(block, dict):
        return []
    now = now or datetime.now(timezone.utc)
    available = count(block.get("available"))
    live = []
    details = block.get("credits")
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        date = expiry(item.get("expires_at"))
        if date and date <= now:
            available = max(0, available - count(item.get("count")))
        else:
            live.append((item, date))
    if not available:
        return []
    lines = [f"Reset credits: {available} available"]
    for item, date in live:
        amount = count(item.get("count"))
        title = item.get("title") or "Reset credit"
        lines.append((f"{amount} × " if amount > 1 else "") + title)
        if date:
            seconds = max(0, int((date - now).total_seconds()))
            days, remaining = divmod(seconds, 86400)
            hours, remaining = divmod(remaining, 3600)
            duration = f"{days}d {hours}h" if days else f"{hours}h {remaining // 60}m" if hours else f"{remaining // 60}m"
            local = date.astimezone()
            stamp = local.strftime("%b %d, %H:%M" if local.year == now.astimezone().year else "%b %d, %Y %H:%M")
            lines.append(f"Expires {stamp} · {duration} left")
        else:
            lines.append("Expiry not provided")
    if not live:
        lines.append("Expiry not provided")
    return lines
