from core.metered import amount_metric, number, parse_json, reset_seconds


def _ratio_metric(amount, detail, period, limit, reset=None):
    metric = amount_metric(amount, "USD", detail, period, limit, reset)
    if number(metric.get("limit")) is not None:
        metric["value_format"] = "amount_ratio"
    # Finite inputs can still overflow when their ratio is extreme.
    if number(metric.get("percentage")) is None:
        metric["percentage"] = None
    return metric


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
            metrics.append(_ratio_metric(limit - remaining, f"Key spend / {reset or 'total'} key limit", period, limit))
        monthly = number(key.get("usage_monthly"))
        if monthly is not None:
            metrics.append(amount_metric(monthly, "USD", "Month spend (this key)", "monthly"))
        elif not metrics and number(key.get("usage")) is not None:
            metrics.append(amount_metric(key["usage"], "USD", "Total spend (this key)"))
        budget = key.get("effective_budget")
        if isinstance(budget, dict) and number(budget.get("spend_usd")) is not None:
            period = {"monthly": "monthly", "weekly": "weekly"}.get(budget.get("reset_interval"), "generic")
            metrics.append(_ratio_metric(budget["spend_usd"], "Effective organization budget", period,
                                         budget.get("limit_usd"), reset_seconds(budget.get("resets_at"))))
        free = key.get("free_model_daily_requests")
        if isinstance(free, dict) and number(free.get("used")) is not None:
            metrics.append(amount_metric(free["used"], "requests", "Free model daily requests", limit=free.get("limit")))
    credits = raw.get("credits")
    credits = credits.get("data") if isinstance(credits, dict) else None
    if isinstance(credits, dict):
        total, spent = number(credits.get("total_credits")), number(credits.get("total_usage"))
        if total is not None and spent is not None and total >= 0 and spent >= 0:
            # Both values are account totals. Key usage has a different scope.
            metrics.append(_ratio_metric(spent, "Account spend / total credits", "credits", total))
            metrics.append(amount_metric(total - spent, "USD", "Account credit balance", "credits"))
    metadata = raw.get("_ai_status")
    if isinstance(metadata, dict) and metadata.get("credits_hint") and not isinstance(credits, dict):
        for metric in metrics:
            metric["detail"] += " · Set OPENROUTER_MANAGEMENT_KEY to track account credits."
    return {"provider": "OpenRouter", "metrics": metrics}
