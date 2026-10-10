"""Pair quota gauges only when their authoritative scope/window matches."""
import re

from core.metered import amount_metric, number, parse_json, reset_seconds


_SERVICES = {
    "compute.googleapis.com": "Compute Engine",
    "aiplatform.googleapis.com": "Vertex AI",
    "bigquery.googleapis.com": "BigQuery",
    "storage.googleapis.com": "Cloud Storage",
    "run.googleapis.com": "Cloud Run",
    "pubsub.googleapis.com": "Pub/Sub",
}
_QUOTAS = {"cpus": "vCPUs", "ssd_total_storage": "SSD storage"}


def _readable(value):
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(value))
    return " / ".join(part.strip().replace("_", " ").capitalize()
                      for part in value.split("/") if part.strip())


def _quota_name(resource, labels):
    quota = str(labels.get("quota_metric") or "quota")
    prefix, _, path = quota.partition("/")
    if not prefix.endswith(".googleapis.com"):
        path = quota
    service = str(resource.get("service") or (prefix if prefix.endswith(".googleapis.com") else ""))
    service_name = _SERVICES.get(service) or _readable(service.split(".")[0])
    quota_name = _QUOTAS.get(path) or _readable(path) or "Quota"
    return " · ".join(part for part in (service_name, quota_name) if part)


def _latest(series):
    points = series.get("points") or []
    if not isinstance(points, list):
        return None, None
    points = [p for p in points if isinstance(p, dict) and isinstance(p.get("interval"), dict)]
    if not points:
        return None, None
    point = max(points, key=lambda p: str(p["interval"].get("endTime", "")))
    value = point.get("value") or {}
    return number(value.get("int64Value", value.get("doubleValue"))) if isinstance(value, dict) else None, point["interval"].get("endTime")


def _scope(series, windowed=False):
    resource = series.get("resource") or {}
    metric = series.get("metric") or {}
    if not isinstance(resource, dict) or not isinstance(metric, dict):
        return None
    labels = metric.get("labels") or {}
    resources = resource.get("labels") or {}
    if not isinstance(labels, dict) or not isinstance(resources, dict) or not labels.get("quota_metric"):
        return None
    key = (resource.get("type"), tuple(sorted(resources.items())), labels["quota_metric"])
    return key + (labels.get("limit_name"), labels.get("window_size")) if windowed else key


def _quotas(data, usage_kind, limit_kind, windowed=False):
    limits = {}
    for series in data.get(limit_kind, []):
        if not isinstance(series, dict):
            continue
        key = _scope(series, windowed)
        value, _ = _latest(series)
        if key is not None and value is not None:
            limits.setdefault(key, []).append(value)
    usages = {}
    for series in data.get(usage_kind, []):
        if not isinstance(series, dict):
            continue
        key = _scope(series, windowed)
        value, observed = _latest(series)
        if key is None or value is None:
            continue
        labels = (series.get("metric") or {}).get("labels") or {}
        # ratev2 metrics may be split by API method, but different windows must
        # never be summed together (or divided by an unrelated limit).
        window = labels.get("window_start_time") if windowed else None
        usages.setdefault((key, window), []).append((value, observed, labels))
    metrics = []
    newest_windows = {}
    if windowed:
        for key, window in usages:
            if window is not None:
                newest_windows[key] = max(str(window), newest_windows.get(key, ""))
    for (key, window), observations in usages.items():
        if windowed and window is not None and str(window) != newest_windows.get(key):
            continue
        candidates = limits.get(key, [])
        limit = candidates[0] if len(candidates) == 1 else None
        labels = observations[0][2]
        resource = dict(key[1])
        detail = " · ".join((str(resource.get("project_id") or "project"),
                             str(resource.get("location") or "global")))
        # Allocation gauges sharing an indistinguishable scope are ambiguous;
        # expose each amount separately instead of summing a possibly repeated gauge.
        groups = [observations] if windowed else [[item] for item in observations]
        for index, group in enumerate(groups):
            metric = amount_metric(sum(item[0] for item in group), "quota units", detail, limit=limit)
            name_parts = [str(resource.get("project_id") or "project"), str(resource.get("service") or "service"),
                          str(labels.get("quota_metric") or "quota"), str(resource.get("location") or "global")]
            name_parts.extend(str(labels[field]) for field in ("limit_name", "window_size") if labels.get(field))
            if len(groups) > 1:
                name_parts.append(str(index + 1))
            # Keep the previous identity so saved selections survive label changes.
            metric["id"] = " · ".join(name_parts)
            display_parts = [_quota_name(resource, labels)]
            if labels.get("limit_name"):
                display_parts.append(_readable(labels["limit_name"]))
            if labels.get("window_size"):
                display_parts.append(str(labels["window_size"]))
            if len(groups) > 1:
                display_parts.append(str(index + 1))
            metric["name"] = " · ".join(display_parts)
            metric["observed_at"] = max(str(item[1] or "") for item in group)
            if window:
                metric["window_start"] = window
            metrics.append(metric)
    return metrics


def parse(raw_output):
    data = parse_json(raw_output)
    metrics = []
    metadata = data.get("_ai_status") or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    rows = data.get("billing_rows")
    if isinstance(rows, list):
        for row in rows:
            cells = row.get("f") if isinstance(row, dict) else None
            if not isinstance(cells, list) or len(cells) != 2 or not all(isinstance(c, dict) for c in cells):
                continue
            currency, amount = cells[0].get("v"), number(cells[1].get("v"))
            if not isinstance(currency, str) or amount is None:
                continue
            budget = metadata.get("monthly_budget") if currency.upper() == str(metadata.get("budget_currency", "USD")).upper() else None
            detail = "Exported month costs after credits" + (" / configured budget" if number(budget) and number(budget) > 0 else "")
            metrics.append(amount_metric(amount, currency.upper(), detail, "monthly", budget, reset_seconds(metadata.get("reset_at"))))
        # No rows can mean export lag or disabled exports; do not fabricate zero.
    if isinstance(data.get("allocation/usage"), list) and isinstance(data.get("limit"), list):
        metrics.extend(_quotas(data, "allocation/usage", "limit"))
    if isinstance(data.get("ratev2/net_usage"), list) and isinstance(data.get("ratev2/limit"), list):
        metrics.extend(_quotas(data, "ratev2/net_usage", "ratev2/limit", True))
    return {"provider": "Google Cloud", "metrics": metrics}
