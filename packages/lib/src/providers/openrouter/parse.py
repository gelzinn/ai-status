import math

from core.metered import amount_metric, number, parse_json, reset_seconds


def _ratio_metric(amount, detail, period, limit, reset=None):
    metric = amount_metric(amount, "USD", detail, period, limit, reset)
    if number(metric.get("limit")) is not None:
        metric["value_format"] = "amount_ratio"
    # Finite inputs can still overflow when their ratio is extreme.
    if number(metric.get("percentage")) is None:
        metric["percentage"] = None
    return metric


def _display_metric(metric, name, detail="", order=None):
    # Keep saved selections independent of the shorter display label.
    metric.update(id=metric["name"], name=name, detail=detail)
    if order is not None:
        metric["display_order"] = order
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
        capped_spend = None
        if limit is not None and limit > 0 and remaining is not None:
            capped_spend = number(limit - remaining)
            metrics.append(_display_metric(
                _ratio_metric(capped_spend, f"Key spend / {reset or 'total'} key limit", period, limit),
                f"Key · {reset or 'total'}"))
        monthly = number(key.get("usage_monthly"))
        if monthly is not None:
            duplicate = reset == "monthly" and capped_spend is not None and math.isclose(monthly, capped_spend, rel_tol=0, abs_tol=1e-9)
            if not duplicate:
                detail = "Reported separately from cap" if reset == "monthly" and capped_spend is not None else ""
                metrics.append(_display_metric(amount_metric(monthly, "USD", "Month spend (this key)", "monthly"),
                                               "Monthly key spend", detail))
        elif not metrics and number(key.get("usage")) is not None:
            metrics.append(_display_metric(amount_metric(key["usage"], "USD", "Total spend (this key)"), "Total key spend"))
        budget = key.get("effective_budget")
        if isinstance(budget, dict) and number(budget.get("spend_usd")) is not None:
            period = {"monthly": "monthly", "weekly": "weekly"}.get(budget.get("reset_interval"), "generic")
            metrics.append(_display_metric(
                _ratio_metric(budget["spend_usd"], "Effective organization budget", period,
                              budget.get("limit_usd"), reset_seconds(budget.get("resets_at"))),
                "Organization budget"))
        free = key.get("free_model_daily_requests")
        if isinstance(free, dict) and number(free.get("used")) is not None:
            metrics.append(_display_metric(amount_metric(free["used"], "requests", "Free model daily requests", limit=free.get("limit")),
                                           "Free requests · daily"))
    credits = raw.get("credits")
    credits = credits.get("data") if isinstance(credits, dict) else None
    if isinstance(credits, dict):
        total, spent = number(credits.get("total_credits")), number(credits.get("total_usage"))
        if total is not None and spent is not None and total >= 0 and spent >= 0:
            # Both values are account totals. Key usage has a different scope.
            metrics.append(_display_metric(_ratio_metric(spent, "Account spend / total credits", "credits", total),
                                           "Account credits", "Spent / total purchased", -2))
            metrics.append(_display_metric(amount_metric(total - spent, "USD", "Account credit balance", "credits"),
                                           "Available balance", order=-1))
    metadata = raw.get("_ai_status")
    if metrics and isinstance(metadata, dict) and metadata.get("credits_hint") and not isinstance(credits, dict):
        metric = metrics[0]
        hint = "Set OPENROUTER_MANAGEMENT_KEY to track account credits."
        metric["detail"] = f"{metric['detail']} · {hint}" if metric["detail"] else hint
    return {"provider": "OpenRouter", "metrics": metrics}
