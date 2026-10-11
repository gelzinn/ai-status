"""Read-only API collector helpers and honest amounts without invented limits."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path
from urllib.parse import urlencode

from .provider_http import QueryError, request


def options():
    try:
        value = json.loads(os.environ.get("AI_STATUS_ACCOUNT_OPTIONS", "{}"))
    except (ValueError, TypeError):
        raise QueryError("Account options must be a JSON object.") from None
    if not isinstance(value, dict):
        raise QueryError("Account options must be a JSON object.")
    return value


def auth_path(default):
    return Path(os.environ.get("AI_STATUS_AUTH_FILE") or default).expanduser()


def parse_json(raw):
    try:
        value = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def json_request(url, headers=None, params=None, method="GET", data=None):
    """JSON payloads are encoded automatically; bytes allow form-encoded bodies."""
    headers = {"Accept": "application/json", **(headers or {})}
    if params:
        url += ("&" if "?" in url else "?") + urlencode(params, doseq=True)
    if isinstance(data, (dict, list)):
        data = json.dumps(data, allow_nan=False).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    elif isinstance(data, str):
        data = data.encode("utf-8")
    try:
        raw = request(url, headers) if method == "GET" and data is None else request(url, headers, method=method, data=data)
        result = json.loads(raw)
    except (ValueError, TypeError):
        raise QueryError("Usage API returned an invalid JSON response.") from None
    if not isinstance(result, (dict, list)):
        raise QueryError("Usage API returned an invalid JSON response.")
    if isinstance(result, dict) and result.get("error"):
        raise QueryError("Usage API returned an error; check account permissions and configuration.")
    return result


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def amount_metric(amount, unit, detail, metric_type="generic", limit=None, reset_in_seconds=None):
    amount, limit = number(amount), number(limit)
    result = {"type": metric_type, "name": f"{detail} ({unit})", "percentage": None, "amount": amount, "unit": unit,
              "detail": detail, "reset_in_seconds": reset_in_seconds}
    if amount is not None and limit is not None and limit > 0:
        result.update(percentage=round(amount / limit * 100, 2), limit=limit)
    return result


def month_window(now=None):
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, now, end


def iso_time(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def reset_seconds(timestamp):
    try:
        end = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return max(0, round((end - datetime.now(timezone.utc)).total_seconds()))
    except (TypeError, ValueError, AttributeError):
        return None


def paginated(url, headers, params, items="data", more="has_more", cursor="next_page", page_param="page"):
    """Never turn a truncated/repeated page into an apparently complete total."""
    result, seen = [], set()
    params = dict(params)
    for _ in range(100):
        page = json_request(url, headers, params)
        if not isinstance(page, dict) or not isinstance(page.get(items), list):
            raise QueryError("Usage API returned an invalid collection response.")
        result.extend(page[items])
        token = page.get(cursor)
        if not page.get(more):
            return result
        if not isinstance(token, str) or not token or token in seen:
            raise QueryError("Usage API pagination is incomplete; retry later.")
        seen.add(token)
        params[page_param] = token
    raise QueryError("Usage API returned too many pages; narrow the account scope.")


def cost_metrics(raw, provider, cents=False):
    """Sum authoritative reported costs, retaining each currency separately."""
    data = parse_json(raw)
    if not isinstance(data.get("data"), list):
        return {"provider": provider, "metrics": []}
    metadata = data.get("_ai_status") or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    workspace = metadata.get("workspace_id")
    totals = {}
    malformed = False
    for bucket in data["data"]:
        if not isinstance(bucket, dict) or not isinstance(bucket.get("results"), list):
            malformed = True
            continue
        for row in bucket["results"]:
            if not isinstance(row, dict):
                malformed = True
                continue
            if workspace and row.get("workspace_id") != workspace:
                continue
            amount = row.get("amount")
            currency = row.get("currency") if cents else (amount.get("currency") if isinstance(amount, dict) else None)
            value = amount if cents else (amount.get("value") if isinstance(amount, dict) else None)
            try:
                value = Decimal(str(value))
                if not value.is_finite() or not isinstance(currency, str) or not currency:
                    raise InvalidOperation
            except (InvalidOperation, ValueError, TypeError):
                malformed = True
                continue
            currency = currency.upper()
            totals[currency] = totals.get(currency, Decimal(0)) + value / (100 if cents else 1)
    if malformed:
        return {"provider": provider, "metrics": []}
    # An authoritative empty report means no reported costs (not a credit balance).
    if not totals:
        totals = {"USD": Decimal(0)}
    metrics = []
    for currency, amount in sorted(totals.items()):
        budget = metadata.get("monthly_budget") if currency == str(metadata.get("budget_currency", "USD")).upper() else None
        detail = "Reported month costs" + (" / configured budget" if number(budget) and number(budget) > 0 else "")
        metrics.append(amount_metric(amount, currency, detail, "monthly", budget, reset_seconds(metadata.get("reset_at"))))
    return {"provider": provider, "metrics": metrics}
