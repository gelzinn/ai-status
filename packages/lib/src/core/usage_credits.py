"""Monetary credit balances, separate from quota windows and saved reset counts."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import math


MAX_OBSERVATION_AGE = 600


def _money(value):
    # USD fields are dollars already. Strings and booleans are not API amounts.
    if type(value) not in (int, float):
        return None
    try:
        if not math.isfinite(float(value)):
            return None
        amount = Decimal(str(value))
        return amount if amount.is_finite() and amount >= 0 else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def _expiry(value):
    if not isinstance(value, str):
        return None
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # A promotion's expiration needs an instant, not an inferred local date.
        return date.astimezone(timezone.utc) if date.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _timestamp(date):
    return date.isoformat().replace("+00:00", "Z") if date else None


def from_claude(usage):
    """Decode Claude's optional iguana_necktie USD promotion without plan gates."""
    block = usage.get("iguana_necktie") if isinstance(usage, dict) else None
    if not isinstance(block, dict):
        return None
    limit = _money(block.get("limit_dollars"))
    if limit is None or limit <= 0:
        return None
    used, remaining = (_money(block.get(key)) for key in ("used_dollars", "remaining_dollars"))
    for key, amount in (("used_dollars", used), ("remaining_dollars", remaining)):
        if block.get(key) is not None and (amount is None or amount > limit):
            return None
    if remaining is None:
        if used is None:
            return None
        remaining = limit - used
    expires = block.get("resets_at")
    date = _expiry(expires)
    if expires is not None and date is None:
        return None
    reason = block.get("locked_reason")
    if reason is not None and not isinstance(reason, str):
        return None
    # Prefer the authoritative balance and preserve separately reported usage.
    # These dollars never become quota consumption. Never persist reasons.
    return {"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
            "balance": float(remaining), "limit": float(limit), "used": float(used if used is not None else limit - remaining),
            "expires_at": _timestamp(date), "available": not bool(reason and reason.strip())}


def _normalized(item):
    """Reject damaged cached optional data without affecting ordinary usage."""
    if not isinstance(item, dict) or item.get("currency") != "USD":
        return None
    identity, title = item.get("id"), item.get("title")
    if not isinstance(identity, str) or not identity.strip() or not isinstance(title, str) or not title.strip():
        return None
    balance = _money(item.get("balance"))
    limit = _money(item.get("limit"))
    used = _money(item.get("used"))
    if balance is None or type(item.get("available", True)) is not bool:
        return None
    if item.get("limit") is not None and (limit is None or limit <= 0 or balance > limit):
        return None
    if item.get("used") is not None and (used is None or limit is not None and used > limit):
        return None
    date = _expiry(item.get("expires_at"))
    if item.get("expires_at") is not None and date is None:
        return None
    return {"id": identity[:120], "title": " ".join(title.split())[:120], "currency": "USD",
            "balance": float(balance), "limit": float(limit) if limit is not None else None,
            "used": float(used) if used is not None else None, "expires_at": _timestamp(date),
            "available": item.get("available", True)}


def _items(entry):
    items = entry.get("monetary_credits") if isinstance(entry, dict) else None
    if not isinstance(items, list) or len(items) > 50:
        return []
    rows = []
    seen = set()
    for item in items:
        row = _normalized(item)
        if row and row["id"] not in seen:
            rows.append(row)
            seen.add(row["id"])
    return rows


def has_credit_data(entry):
    """Recognize valid optional balances, including exhausted or locked ones."""
    return bool(_items(entry))


def _observation(entry, now):
    observed = entry.get("_observed_at")
    try:
        known = type(observed) in (int, float) and math.isfinite(observed) and observed > 0
    except OverflowError:
        known = False
    stale = bool(entry.get("_cached") or entry.get("_error") or entry.get("error") or not known)
    if known:
        stale = stale or observed > now.timestamp() + 5 or now.timestamp() - observed > MAX_OBSERVATION_AGE
    date = None
    if known:
        try:
            date = datetime.fromtimestamp(observed, timezone.utc)
        except (ValueError, OverflowError, OSError):
            stale = True
    return stale, date


def presentation(entry, now=None):
    """Compute states at display time so offline expirations cannot stay usable."""
    now = now or datetime.now(timezone.utc)
    stale, observation = _observation(entry, now) if isinstance(entry, dict) else (False, None)
    rows = []
    for item in _items(entry):
        date = _expiry(item["expires_at"])
        expired = date is not None and date <= now
        status = ("expired" if expired else "unavailable" if stale or not item["available"]
                  else "exhausted" if item["balance"] == 0 else "available")
        balance = item["balance"] if status in ("available", "exhausted") else None
        value = f"${balance:.2f}" if balance is not None else status.capitalize()
        details = [status.capitalize()]
        details.append(f"{'Expired' if expired else 'Expires'} {_timestamp(date)}" if date else "Expiration not reported")
        if balance is None:
            details.append(f"Last observed ${item['balance']:.2f}")
        if stale:
            details.append(f"Observed {_timestamp(observation)}" if observation else "Observation time unavailable")
            details.append("Refresh unavailable" if entry.get("_cached") or entry.get("_error") or entry.get("error")
                           else "Observation is stale")
        rows.append({**item, "balance": balance, "observed_balance": item["balance"], "status": status,
                     "value": value, "detail": " · ".join(details), "stale": stale})
    return rows


def metrics(entry, now=None):
    """Adapt balances to the existing amount rows without feeding quota math."""
    return [{"type": "credits", "id": row["id"], "name": row["title"], "percentage": None,
             "amount": row["balance"], "unit": row["currency"], "value": row["value"], "detail": row["detail"]}
            for row in presentation(entry, now)]


def display_lines(entry, now=None):
    return [line for row in presentation(entry, now)
            for line in (f"{row['title']}: {row['value']}", row["detail"])]
