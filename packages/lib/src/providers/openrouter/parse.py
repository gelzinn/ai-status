from core.metered import amount_metric, number, parse_json, reset_seconds


def parse(raw_output):
    raw = parse_json(raw_output)
    key = raw.get("key", raw)
    key = key.get("data") if isinstance(key, dict) else None
    metrics = []
    if isinstance(key, dict):
        limit, remaining = number(key.get("limit")), number(key.get("limit_remaining"))
        reset = key.get("limit_reset")
        period = {"monthly": "monthly", "weekly": "weekly", "daily": "generic"}.get(reset, "generic")
        if limit is not None and limit > 0 and remaining is not None:
            metrics.append(amount_metric(limit - remaining, "USD", f"Key spend / {reset or 'total'} key limit", period, limit))
        monthly = number(key.get("usage_monthly"))
        if monthly is not None:
            metrics.append(amount_metric(monthly, "USD", "Month spend (this key)", "monthly"))
        elif not metrics and number(key.get("usage")) is not None:
            metrics.append(amount_metric(key["usage"], "USD", "Total spend (this key)"))
        budget = key.get("effective_budget")
        if isinstance(budget, dict) and number(budget.get("spend_usd")) is not None:
            period = {"monthly": "monthly", "weekly": "weekly"}.get(budget.get("reset_interval"), "generic")
            metrics.append(amount_metric(budget["spend_usd"], "USD", "Effective organization budget", period,
                                         budget.get("limit_usd"), reset_seconds(budget.get("resets_at"))))
        free = key.get("free_model_daily_requests")
        if isinstance(free, dict) and number(free.get("used")) is not None:
            metrics.append(amount_metric(free["used"], "requests", "Free model daily requests", limit=free.get("limit")))
    credits = raw.get("credits")
    credits = credits.get("data") if isinstance(credits, dict) else None
    if isinstance(credits, dict):
        total, spent = number(credits.get("total_credits")), number(credits.get("total_usage"))
        if total is not None and spent is not None:
            # Lifetime purchases are not a renewable quota denominator.
            metrics.append(amount_metric(total - spent, "USD", "Account credit balance", "credits"))
    return {"provider": "OpenRouter", "metrics": metrics}
