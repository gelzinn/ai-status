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


def available_credits(block, now=None):
    """Return live details, bounded by the provider's authoritative credit count."""
    if not isinstance(block, dict):
        return {"available": 0, "credits": [], "undetailed": 0}
    now = now or datetime.now(timezone.utc)
    available = count(block.get("available"))
    live = []
    details = block.get("credits")
    for item in details if isinstance(details, list) else []:
        if not isinstance(item, dict):
            continue
        date = expiry(item.get("expires_at"))
        amount = count(item.get("count"))
        if not amount:
            continue
        if date and date <= now:
            available = max(0, available - amount)
        else:
            title = item.get("title")
            live.append({"title": title if isinstance(title, str) and title.strip() else "Reset credit",
                         "count": amount, "expires_at": date})
    remaining = available
    credits = []
    for item in live:
        amount = min(item["count"], remaining)
        if amount:
            credits.append({**item, "count": amount})
            remaining -= amount
    return {"available": available, "credits": credits, "undetailed": remaining}


def format_expiry(date, now=None):
    now = now or datetime.now(timezone.utc)
    seconds = max(0, int((date - now).total_seconds()))
    days, remaining = divmod(seconds, 86400)
    hours, remaining = divmod(remaining, 3600)
    duration = f"{days}d {hours}h" if days else f"{hours}h {remaining // 60}m" if hours else f"{remaining // 60}m"
    local = date.astimezone()
    stamp = local.strftime("%b %d, %H:%M" if local.year == now.astimezone().year else "%b %d, %Y %H:%M")
    return stamp, duration + " left"


def local_timezone(date):
    """Label the system's local UTC offset at the expiration date."""
    offset = date.astimezone().strftime("%z")
    return f"UTC{offset[:3]}:{offset[3:]}"


def local_timezone_summary(dates):
    """Describe the local offsets represented by the available expiration dates."""
    offsets = dict.fromkeys(local_timezone(date) for date in dates if date)
    return "Local time · " + " / ".join(offsets) if offsets else ""


def display_lines(block, now=None):
    data = available_credits(block, now)
    if not data["available"]:
        return []
    lines = [f"Reset credits: {data['available']} available"]
    for item in data["credits"]:
        amount = item["count"]
        title = item["title"]
        lines.append((f"{amount} × " if amount > 1 else "") + title)
        date = item["expires_at"]
        if date:
            stamp, remaining = format_expiry(date, now)
            lines.append(f"Expires {stamp} · {remaining}")
        else:
            lines.append("Expiry not provided")
    if not data["credits"]:
        lines.append("Expiry not provided")
    return lines


def presentation(block, now=None):
    """Plain display fields for the Quickshell panel, using the shared live inventory."""
    data = available_credits(block, now)
    if not data["available"]:
        return None
    details = []
    for item in data["credits"]:
        title = item["title"]
        if item["count"] > 1:
            title += f" ×{item['count']}"
        if item["expires_at"]:
            stamp, remaining = format_expiry(item["expires_at"], now)
            detail = f"Expires {stamp} · {remaining}"
        else:
            detail = "Expiration not reported"
        details.append(f"{title} · {detail}")
    if data["undetailed"]:
        details.append("Expiration not reported")
    rows = []
    credits = data["credits"] + ([{"title": "Reset credit", "count": data["undetailed"], "expires_at": None}]
                                  if data["undetailed"] else [])
    for item in credits:
        date = item["expires_at"]
        stamp, remaining = format_expiry(date, now) if date else ("Not provided", "")
        zone = local_timezone(date) if date else ""
        rows.append({"title": item["title"], "count": item["count"],
                     "expires": stamp, "remaining": remaining, "timezone": zone})
    available = data["available"]
    return {"available": available,
            "summary": f"{available} reset{'s' if available != 1 else ''} available",
            "details": details, "rows": rows, "undetailed": data["undetailed"],
            "timezone": local_timezone_summary(item["expires_at"] for item in data["credits"])}
