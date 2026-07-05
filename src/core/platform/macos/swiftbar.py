from ... import state
from ... import types as _types


def _format_reset_time(seconds):
    if seconds is None:
        return ""
    seconds = max(0, int(seconds))
    if seconds == 0:
        return "Resets now"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    if days > 0:
        return f"Resets in {days}d {hours}h"
    if hours > 0:
        return f"Resets in {hours}h {minutes}m"
    return f"Resets in {minutes}m"


def render(latest_data, selected):
    lines = []

    selected_provider = selected.get("provider") if selected else None
    selected_idx = selected.get("idx", 0) if selected else None
    selected_metric = selected.get("metric") if selected else None

    title_text = _title_line(latest_data, selected)
    if title_text:
        lines.append(f"{title_text} | size=12 dropdown=false")
    else:
        lines.append("AI Status | size=12 dropdown=false")

    lines.append("---")

    if not latest_data:
        lines.append("No data | size=11")
        lines.append("Waiting for first fetch... | size=10")
        lines.append("---")
        lines.append("Refresh Now | bash=ai-status swiftbar-refresh terminal=false refresh=true")
        return "\n".join(lines)

    for p in latest_data:
        provider = p.get("provider", "AI Provider")
        metrics = p.get("metrics", [])
        if not metrics:
            continue

        dir_name = p.get("_dir")
        idx = p.get("_idx", 0)
        is_selected = dir_name == selected_provider and idx == selected_idx
        prefix = "→ " if is_selected else "  "
        error = p.get("_error")

        provider_line = f"{prefix}{provider}"
        if error:
            provider_line += " ● (stale)"
        lines.append(f"`{provider_line}` | size=11")

        sorted_metrics = sorted(metrics, key=lambda m: _types.TYPE_ORDER.get(m.get("type", "generic"), 4))
        for metric in sorted_metrics:
            mtype = metric.get("type", "generic")
            name = _types.TYPE_NAMES.get(mtype, "Usage")
            pct = float(metric.get("percentage", 0.0))
            seconds = metric.get("reset_in_seconds")
            detail = metric.get("detail")
            if detail is None:
                detail = _format_reset_time(seconds)

            is_active = is_selected and mtype == selected_metric
            bullet = "•" if is_active else " "
            lines.append(f"{bullet} {name}: | size=11")
            lines.append(f"--{_types.make_progress_bar(pct)} | size=11")
            if detail:
                lines.append(f"---{detail} | size=10")
        lines.append("---")

    lines.append("Refresh | bash=ai-status swiftbar-refresh terminal=false refresh=true")
    lines.append("Settings | bash=ai-status config terminal=true")

    return "\n".join(lines)


def _title_line(latest_data, selected):
    if not selected or not latest_data:
        return None
    dir_name = selected.get("provider")
    idx = selected.get("idx", 0)
    metric_type = selected.get("metric", "rolling")
    count = 0
    for p in latest_data:
        if p.get("_dir") == dir_name:
            if count == idx:
                provider_name = p.get("provider", "")
                for m in p.get("metrics", []):
                    if m.get("type") == metric_type:
                        pct = float(m.get("percentage", 0.0))
                        return f"{provider_name} {pct:.0f}%"
                if p.get("metrics"):
                    pct = float(p["metrics"][0].get("percentage", 0.0))
                    return f"{provider_name} {pct:.0f}%"
                return provider_name
            count += 1
    return None
