import re
import math
from html import escape
from . import fetch
from . import state
from . import usage_credits, config
from .reset_credits import display_lines as reset_credit_lines

TYPE_NAMES = {
    "rolling": "Rolling Usage",
    "daily": "Daily Usage",
    "weekly": "Weekly Usage",
    "monthly": "Monthly Usage",
    "credits": "Available balance",
    "balance": "Available balance",
    "generic": "Usage",
}

TYPE_ORDER = {"rolling": 0, "daily": 1, "weekly": 2, "monthly": 3, "generic": 4}

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
BAR_LINE_WIDTH = 34

ICON = "\U000f06a9"

DIM_INACTIVE = 55   # non-selected providers and inactive metrics
DIM_RESET = 60      # reset lines


def connection_key(entry):
    return entry.get("_connection_id") or entry.get("_dir")


def entry_name(entry):
    name = entry.get("provider", "AI Provider")
    label = entry.get("_account_label")
    return f"{name} · {label}" if label else name


def entry_metrics(entry):
    """Project live monetary-credit states into the existing selectable rows."""
    source = entry.get("metrics")
    metrics = [metric for metric in source if isinstance(metric, dict)] if isinstance(source, list) else []
    credits = usage_credits.metrics(entry)
    keys = {metric_key(metric) for metric in credits}
    # Snapshot adapters may already have projected these rows. Recompute their
    # states from the original observation instead of duplicating stale rows.
    return [metric for metric in metrics if metric_key(metric) not in keys] + credits


def metric_percentage(metric, selected=None):
    if isinstance(metric.get("percentage"), bool):
        return None
    try:
        value = float(metric.get("percentage"))
        if not math.isfinite(value):
            return None
        if state.get_usage_display(selected) == "remaining":
            return max(0.0, min(100.0, 100.0 - value))
        return value
    except (ValueError, TypeError, OverflowError):
        return None


def _metric_ratio(metric):
    if metric.get("value_format") != "amount_ratio":
        return None
    if any(isinstance(metric.get(key), bool) for key in ("amount", "limit")):
        return None
    try:
        amount, limit = float(metric.get("amount")), float(metric.get("limit"))
        if math.isfinite(amount) and math.isfinite(limit) and limit > 0:
            return amount, limit
    except (ValueError, TypeError, OverflowError):
        pass
    return None


def _shows_remaining(metric, selected):
    # Wallet values already represent the real balance. The preference still
    # changes their progress bar, but must not invert or relabel the dollars.
    if metric.get("value_format") == "credit_balance":
        return False
    # Provider percentages are normalized to consumption, including credit
    # ratios. Balances and uncapped spend have no percentage to complement.
    return state.get_usage_display(selected) == "remaining" and (
        metric_percentage(metric) is not None or _metric_ratio(metric) is not None
    )


def metric_value(metric, selected=None):
    unit = metric.get("unit", "")
    if metric.get("value_format") == "credit_balance":
        if isinstance(metric.get("balance"), bool):
            return "Unavailable"
        try:
            balance = float(metric.get("balance"))
            if not math.isfinite(balance):
                return "Unavailable"
        except (TypeError, ValueError, OverflowError):
            return "Unavailable"
        return f"${balance:.2f}" if unit == "USD" else f"{balance:,.2f} {unit}".strip()
    ratio = _metric_ratio(metric)
    if ratio is not None:
        amount, limit = ratio
        if _shows_remaining(metric, selected):
            amount = max(0.0, min(limit, limit - amount))
        if not state.get_show_total(selected):
            return f"${amount:.2f}" if unit == "USD" else f"{amount:,.2f} {unit}".strip()
        if unit == "USD":
            return f"${amount:.2f} / ${limit:.2f}"
        return f"{amount:,.2f} / {limit:,.2f} {unit}".strip()
    percentage = metric_percentage(metric, selected)
    if percentage is not None:
        return f"{percentage:.0f}%"
    try:
        amount = float(metric.get("amount"))
        if not math.isfinite(amount):
            return "Unavailable"
    except (ValueError, TypeError):
        return str(metric.get("value") or "Unavailable")
    return f"${amount:.2f}" if unit == "USD" else f"{amount:,.2f} {unit}".strip()


def metric_title(metric, selected=None):
    title = metric.get("title") or metric.get("name") or TYPE_NAMES.get(metric.get("type", "generic"), "Usage")
    unit = metric.get("unit")
    if unit and (metric_percentage(metric) is None or metric.get("value_format") in ("amount_ratio", "credit_balance")):
        title = title.removesuffix(f" ({unit})")
    if _shows_remaining(metric, selected):
        # Some providers embed the used amount in their label. Keep that
        # factual breakdown in detail instead of relabeling it as remaining.
        title = re.sub(r":\s*\$[\d.,]+ of \$[\d.,]+ used(?:\s+\([^)]+\))?$", "", title)
        title, count = re.subn(
            r"\b(usage|used|spend|spent)\b",
            lambda match: "Remaining" if match[0][0].isupper() else "remaining",
            title, flags=re.IGNORECASE,
        )
        if not count:
            title += " remaining"
    return title


def metric_detail(metric):
    detail = metric.get("detail")
    if detail is None:
        if metric_is_amount(metric) and metric.get("reset_in_seconds") is None:
            return ""
        return format_reset_time(metric.get("reset_in_seconds"), metric.get("type"))
    name = metric.get("name") or ""
    unit = metric.get("unit")
    if unit:
        name = name.removesuffix(f" ({unit})")
    if detail.strip().casefold() in {name.strip().casefold(), metric_title(metric).strip().casefold()}:
        return ""
    return detail


def metric_sort_key(metric):
    order = metric.get("display_order")
    return order if type(order) is int else TYPE_ORDER.get(metric.get("type", "generic"), 4)


def metric_is_amount(metric):
    if metric_percentage(metric) is not None or isinstance(metric.get("amount"), bool):
        return False
    try:
        return math.isfinite(float(metric.get("amount")))
    except (TypeError, ValueError, OverflowError):
        return False


def _dim(text, alpha):
    return f"<span alpha='{alpha}%'>{text}</span>"


def metric_key(metric):
    """Stable per-metric id within a provider. Normally just the type, but when
    a provider exposes two metrics of the same type (e.g. Claude's general vs
    Fable weekly limit) the label prefix in ``detail`` disambiguates them so
    each can be selected independently. Explicit provider identities preserve
    selections when display labels change."""
    t = metric.get("type", "generic")
    identity = metric.get("id")
    if isinstance(identity, str) and identity:
        return f"{t}:{identity}"
    if metric.get("name"):
        return f"{t}:{metric['name']}"
    detail = metric.get("detail") or ""
    if " · " in detail:
        label = detail.split(" · ", 1)[0].strip()
        if label:
            return f"{t}:{label}"
    return t


def _find_selected_provider(latest_data, selected):
    if not selected or not latest_data:
        return None
    dir_name = selected.get("provider")
    idx = selected.get("idx", 0)
    count = 0
    for p in latest_data:
        if connection_key(p) == dir_name:
            if p.get("_idx", count) == idx:
                return p
            count += 1
    return None


def get_bar_metric_choices(latest_data, selected):
    """Resolve pinned identities without turning missing metrics into duplicates."""
    if "items" in (selected or {}):
        enabled = config.enabled_connection_order()
        latest_data = [entry for entry in latest_data if connection_key(entry) in enabled]
    choices = []
    for choice in state.get_selected_items(selected):
        provider = _find_selected_provider(latest_data, choice)
        if provider and choice["metric"] in [metric_key(metric) for metric in usable_metrics(provider)]:
            choices.append(choice)
    if not choices and "items" not in (selected or {}):
        for provider in latest_data:
            metrics = sorted(entry_metrics(provider), key=metric_sort_key)
            if metrics:
                choices.append({"provider": connection_key(provider), "idx": provider.get("_idx", 0),
                                "metric": metric_key(metrics[0])})
                break
    return choices


def usable_metrics(entry):
    """Selectable observations, excluding failed placeholders and invalid values."""
    if fetch._is_error_result(entry):
        return []
    return [metric for metric in entry_metrics(entry)
            if (metric_percentage(metric) is not None if metric.get("percentage") is not None
                else metric_is_amount(metric) or isinstance(metric.get("value"), str) and bool(metric["value"]))]


def get_selected_metric_text(latest_data, selected, spinner=None, pending=None):
    if "items" not in (selected or {}):
        return _get_single_metric_text(latest_data, selected, spinner)
    choices = get_bar_metric_choices(latest_data, selected)
    if not choices:
        return "AI Status " + spinner if spinner is not None else "AI Status"
    return " · ".join(_get_single_metric_text(
        latest_data, dict(selected, **choice),
        spinner if pending is None or choice["provider"] in pending else None,
    ) for choice in choices)


def _get_single_metric_text(latest_data, selected, spinner=None):
    p = _find_selected_provider(latest_data, selected)
    show_icon = state.get_icon_mode(selected) == "bot"
    if not p:
        if spinner is not None:
            return f"{ICON} {spinner}" if show_icon else spinner
        return ICON

    provider_full_name = entry_name(p)
    selected_key = selected.get("metric", "rolling")
    metrics = entry_metrics(p)

    show_provider = selected.get("show_provider", True)
    show_model = selected.get("show_model", True)
    show_metric = selected.get("show_metric", False)
    show_pct = selected.get("show_pct", True)

    if not (show_provider or show_model or show_metric or show_pct):
        show_provider = True
        show_pct = True
    
    main_name = provider_full_name
    model_name = ""
    match = re.match(r"^([^(]+)(?:\s*\(([^)]+)\))?$", provider_full_name)
    if match:
        main_name = match.group(1).strip()
        if match.group(2):
            model_name = match.group(2).strip()
            
    m = None
    for item in metrics:
        if metric_key(item) == selected_key:
            m = item
            break
    if not m and metrics:
        m = sorted(metrics, key=metric_sort_key)[0]

    metric_name = metric_title(m, selected) if m else "Usage"

    if spinner is not None:
        # While loading the percentage isn't known yet — show the spinner in
        # its place, forced on so the loading indicator stays visible even when
        # the percentage is configured off.
        pct_str = spinner
        show_pct = True
    elif m:
        pct_str = metric_value(m, selected)
    else:
        pct_str = "0%"

    parts = []
    if show_provider and main_name:
        parts.append(main_name)
    if show_model and model_name:
        if show_provider:
            parts.append(f"({model_name})")
        else:
            parts.append(model_name)
    if show_metric:
        parts.append(metric_name)
    if show_pct:
        parts.append(pct_str)
        
    text = " ".join(parts)
    if show_icon:
        return f"{ICON}\u2003{text}" if text else ICON
    else:
        return text


def make_progress_bar(percentage, width=25):
    percentage = max(0.0, min(100.0, percentage))
    filled_len = int(round(width * percentage / 100))
    bar_chars = []
    for i in range(width):
        if i < filled_len:
            bar_chars.append("█")
        else:
            bar_chars.append("<span alpha='15%'>█</span>")
    bar = "".join(bar_chars)
    return f"[{bar}] {percentage:.0f}%"


def _loading_bar_body(frame_index, width=25):
    """A soft highlight sweeping left -> right over a dim track — the terminal
    analogue of the replica's shimmer gradient. The travel extends far enough
    past both edges that the highlight fully leaves one side before re-entering
    the other, so the loop reads as a continuous sweep rather than a reset.
    Returns the bracketed bar string (no trailing value)."""
    sigma = width / 4.5                          # highlight half-width
    margin = int(round(3.2 * sigma))             # clear the bar before wrapping
    span = width + 2 * margin
    center = (frame_index * 3) % span - margin   # -margin .. width-1+margin
    base, peak = 0.10, 1.0
    bar_chars = []
    for i in range(width):
        d = i - center
        intensity = math.exp(-(d * d) / (2 * sigma * sigma))
        alpha = int(round((base + (peak - base) * intensity) * 100))
        bar_chars.append(f"<span alpha='{alpha}%'>█</span>")
    return "[" + "".join(bar_chars) + "]"


def make_shimmer_bar(frame_index, spinner, width=25):
    # Loading bar: an empty shimmer track with the spinner where the percentage
    # would be — mirrors the replica (hidden fill + shimmer, spinner for number).
    return f"{_loading_bar_body(frame_index, width)} {spinner}"


def make_empty_loading_bar(frame_index, width=25):
    return f"{_loading_bar_body(frame_index, width)} Loading..."


def format_reset_time(seconds, mtype):
    if seconds is None:
        return "<span alpha='50%'>no reset available</span>"

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


def format_provider_block(
    provider_data, selected_dir=None, selected_idx=None, selected_metric=None, selected=None
):
    provider = escape(entry_name(provider_data))
    metrics = entry_metrics(provider_data)
    if not metrics:
        return ""

    pinned_metrics = {item["metric"] for item in state.get_selected_items(selected)
                      if item["provider"] == connection_key(provider_data) and item["idx"] == provider_data.get("_idx", 0)}
    is_selected = bool(pinned_metrics) if "items" in (selected or {}) else (
        connection_key(provider_data) == selected_dir
        and provider_data.get("_idx") == selected_idx
    )
    prefix = "→ " if is_selected else "  "
    if provider_data.get("_error"):
        err_icon = '<span foreground="#ef4444"> ●</span>'
        pad = max(1, BAR_LINE_WIDTH - len(prefix) - len(provider) - 2)
        header = f"{prefix}{provider}{' ' * pad}{err_icon}"
    else:
        header = f"{prefix}{provider}"
    # Dim non-selected providers so the selected one stands out (like the replica)
    if not is_selected:
        header = _dim(header, DIM_INACTIVE)
    sorted_metrics = sorted(metrics, key=metric_sort_key)
    lines = [header, ""]
    for metric in sorted_metrics:
        name = escape(metric_title(metric, selected))
        is_active = metric_key(metric) in pinned_metrics if "items" in (selected or {}) else is_selected and metric_key(metric) == selected_metric
        detail = metric_detail(metric)

        # Only the active metric of the selected provider stays bright.
        recede = None if is_active else DIM_INACTIVE
        label = f"•   {name}:" if is_active else f"    {name}:"
        if recede:
            label = _dim(label, recede)
        percentage = metric_percentage(metric, selected)
        if percentage is not None:
            bar_str = make_progress_bar(percentage)
            if metric.get("value_format") in ("amount_ratio", "credit_balance"):
                bar_str = bar_str.rsplit(" ", 1)[0] + " " + escape(metric_value(metric, selected))
        else:
            bar_str = escape(metric_value(metric, selected))
        bar_line = ("    " + _dim(bar_str, recede)) if recede else f"    {bar_str}"

        lines.append(label)
        lines.append(bar_line)
        if detail:
            lines.append("    " + _dim(detail, recede if recede else DIM_RESET))
        lines.append("")
    for line in reset_credit_lines(provider_data.get("reset_credits")):
        lines.append("    " + _dim(escape(line), DIM_INACTIVE))
    return "\n".join(lines)


def format_loading_provider_block(
    provider_data, frame_index, selected_dir=None, selected_idx=None, selected_metric=None, selected=None
):
    provider = escape(entry_name(provider_data))
    metrics = entry_metrics(provider_data)
    if not metrics:
        return ""

    # Identical layout to format_provider_block (prefix arrow, active bullet,
    # indentation) so nothing shifts when loading resolves — only the bar (a
    # shimmer) and the value (a spinner) differ.
    pinned_metrics = {item["metric"] for item in state.get_selected_items(selected)
                      if item["provider"] == connection_key(provider_data) and item["idx"] == provider_data.get("_idx", 0)}
    is_selected = bool(pinned_metrics) if "items" in (selected or {}) else (
        connection_key(provider_data) == selected_dir
        and provider_data.get("_idx") == selected_idx
    )
    prefix = "→ " if is_selected else "  "
    spinner = SPINNERS[frame_index % len(SPINNERS)]
    if provider_data.get("_error"):
        err_icon = '<span foreground="#ef4444"> ●</span>'
        pad = max(1, BAR_LINE_WIDTH - len(prefix) - len(provider) - 2)
        header = f"{prefix}{provider}{' ' * pad}{err_icon}"
    else:
        header = f"{prefix}{provider}"
    if not is_selected:
        header = _dim(header, DIM_INACTIVE)

    sorted_metrics = sorted(metrics, key=metric_sort_key)
    lines = [header, ""]
    for metric in sorted_metrics:
        name = escape(metric_title(metric, selected))
        is_active = metric_key(metric) in pinned_metrics if "items" in (selected or {}) else is_selected and metric_key(metric) == selected_metric
        detail = metric_detail(metric)

        recede = None if is_active else DIM_INACTIVE
        label = f"•   {name}:" if is_active else f"    {name}:"
        if recede:
            label = _dim(label, recede)
        lines.append(label)
        if metric_percentage(metric) is not None:
            lines.append(f"    {make_shimmer_bar(frame_index, spinner)}")
        else:
            # Cached balances/text statuses have no quota bar to animate.
            value = escape(metric_value(metric, selected)) + " " + spinner
            lines.append("    " + (_dim(value, recede) if recede else value))
        if detail:
            lines.append("    " + _dim(detail, recede if recede else DIM_RESET))
        lines.append("")
    for line in reset_credit_lines(provider_data.get("reset_credits")):
        lines.append("    " + _dim(escape(line), DIM_INACTIVE))
    return "\n".join(lines)


def format_header():
    info = fetch.get_version_info()
    name = "AI Status"
    version = f"v{info['current']}"
    padding = BAR_LINE_WIDTH - len(name) - len(version)
    if padding < 1:
        padding = 1
    line = f"{name}{' ' * padding}{version}"
    if info["has_update"]:
        line += f"\n<span alpha='70%'>Update available: v{info['latest']}</span>"
    return line


def build_loading_state(latest_data, frame, selected=None, pending=None):
    """Render while data is being fetched.

    ``pending`` is the set of provider ``_dir`` names still loading. Providers
    in it animate a loading block; the rest render their final block. This lets
    each provider finish independently — the selected provider (and the module
    text) update the moment it's done, without waiting for the slowest one.
    ``pending=None`` keeps the legacy behaviour (everything loading).
    """
    spinner = SPINNERS[frame % len(SPINNERS)]
    header = format_header()
    sep = f"\n\n{'─' * BAR_LINE_WIDTH}\n"
    selected_dir = selected.get("provider") if selected else None
    selected_idx = selected.get("idx") if selected else None
    selected_metric = selected.get("metric") if selected else None

    def _is_pending(p):
        return True if pending is None else (connection_key(p) in pending)

    if latest_data:
        blocks = []
        for p in latest_data:
            if _is_pending(p):
                block = format_loading_provider_block(
                    p, frame, selected_dir, selected_idx, selected_metric, selected
                )
            else:
                block = format_provider_block(
                    p, selected_dir, selected_idx, selected_metric, selected
                )
            if block:
                blocks.append(block)
        tooltip = f"{header}{sep}\n" + "\n".join(blocks)
    else:
        bar = make_empty_loading_bar(frame)
        tooltip = f"{header}\n\n{'─' * BAR_LINE_WIDTH}\n\n  Loading AI Provider Status {spinner}\n  {bar}"

    # Module text honours the display settings (only the % is swapped for the
    # spinner). Show the spinner only while the *selected* provider is loading;
    # once it's done, show its real percentage even if others still load.
    if pending is None:
        selected_pending = True
    elif selected_dir is not None:
        selected_pending = selected_dir in pending
    else:
        selected_pending = bool(pending)
    text = get_selected_metric_text(latest_data, selected,
                                    spinner=spinner if "items" in (selected or {}) or selected_pending else None,
                                    pending=pending)

    return {
        "text": text,
        "tooltip": tooltip.strip(),
    }


def build_final_state(latest_data, selected=None):
    header = format_header()
    sep = f"\n\n{'─' * BAR_LINE_WIDTH}\n"
    selected_dir = selected.get("provider") if selected else None
    selected_idx = selected.get("idx") if selected else None
    selected_metric = selected.get("metric") if selected else None
    if latest_data:
        blocks = []
        for p in latest_data:
            block = format_provider_block(
                p, selected_dir, selected_idx, selected_metric, selected
            )
            if block:
                blocks.append(block)
        tooltip = f"{header}{sep}\n" + "\n".join(blocks)
    else:
        tooltip = f"{header}\n\n{'─' * BAR_LINE_WIDTH}"

    metric_text = get_selected_metric_text(latest_data, selected)
    return {"text": metric_text, "tooltip": tooltip.strip()}
