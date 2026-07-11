import re
import math
from . import fetch
from . import state

TYPE_NAMES = {
    "rolling": "Rolling Usage",
    "daily": "Daily Usage",
    "weekly": "Weekly Usage",
    "monthly": "Monthly Usage",
    "generic": "Usage",
}

TYPE_ORDER = {"rolling": 0, "daily": 1, "weekly": 2, "monthly": 3, "generic": 4}

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
BAR_LINE_WIDTH = 34

ICON = "\U000f06a9"

DIM_INACTIVE = 55   # non-selected providers and inactive metrics
DIM_RESET = 60      # reset lines


def _dim(text, alpha):
    return f"<span alpha='{alpha}%'>{text}</span>"


def metric_key(metric):
    """Stable per-metric id within a provider. Normally just the type, but when
    a provider exposes two metrics of the same type (e.g. Claude's general vs
    Fable weekly limit) the label prefix in ``detail`` disambiguates them so
    each can be selected independently."""
    t = metric.get("type", "generic")
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
        if p.get("_dir") == dir_name:
            if count == idx:
                return p
            count += 1
    return None


def get_selected_metric_text(latest_data, selected, spinner=None):
    p = _find_selected_provider(latest_data, selected)
    show_icon = state.get_icon_mode(selected) == "bot"
    if not p:
        if spinner is not None:
            return f"{ICON} {spinner}" if show_icon else spinner
        return ICON

    provider_full_name = p.get("provider", "")
    selected_key = selected.get("metric", "rolling")
    metrics = p.get("metrics", [])

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
        m = metrics[0]

    metric_name = TYPE_NAMES.get(m.get("type", "generic"), "Usage") if m else "Usage"

    if spinner is not None:
        # While loading the percentage isn't known yet — show the spinner in
        # its place, forced on so the loading indicator stays visible even when
        # the percentage is configured off.
        pct_str = spinner
        show_pct = True
    elif m:
        pct = float(m.get("percentage", 0.0))
        pct_str = f"{pct:.0f}%"
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
    provider_data, selected_dir=None, selected_idx=None, selected_metric=None
):
    provider = provider_data.get("provider", "AI Provider")
    metrics = provider_data.get("metrics", [])
    if not metrics:
        return ""

    is_selected = (
        provider_data.get("_dir") == selected_dir
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
    sorted_metrics = sorted(
        metrics, key=lambda m: TYPE_ORDER.get(m.get("type", "generic"), 4)
    )
    lines = [header, ""]
    for metric in sorted_metrics:
        mtype = metric.get("type", "generic")
        name = TYPE_NAMES.get(mtype, "Usage")
        is_active = is_selected and metric_key(metric) == selected_metric
        seconds = metric.get("reset_in_seconds")
        detail = metric.get("detail")
        if detail is None:
            detail = format_reset_time(seconds, mtype)

        # Only the active metric of the selected provider stays bright.
        recede = None if is_active else DIM_INACTIVE
        label = f"•   {name}:" if is_active else f"    {name}:"
        if recede:
            label = _dim(label, recede)
        bar_str = make_progress_bar(float(metric.get("percentage", 0.0)))
        bar_line = ("    " + _dim(bar_str, recede)) if recede else f"    {bar_str}"

        lines.append(label)
        lines.append(bar_line)
        if detail:
            lines.append("    " + _dim(detail, recede if recede else DIM_RESET))
        lines.append("")
    return "\n".join(lines)


def format_loading_provider_block(
    provider_data, frame_index, selected_dir=None, selected_idx=None, selected_metric=None
):
    provider = provider_data.get("provider", "AI Provider")
    metrics = provider_data.get("metrics", [])
    if not metrics:
        return ""

    # Identical layout to format_provider_block (prefix arrow, active bullet,
    # indentation) so nothing shifts when loading resolves — only the bar (a
    # shimmer) and the value (a spinner) differ.
    is_selected = (
        provider_data.get("_dir") == selected_dir
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

    sorted_metrics = sorted(
        metrics, key=lambda m: TYPE_ORDER.get(m.get("type", "generic"), 4)
    )
    lines = [header, ""]
    for metric in sorted_metrics:
        mtype = metric.get("type", "generic")
        name = TYPE_NAMES.get(mtype, "Usage")
        is_active = is_selected and metric_key(metric) == selected_metric
        seconds = metric.get("reset_in_seconds")
        detail = metric.get("detail")
        if detail is None:
            detail = format_reset_time(seconds, mtype)

        recede = None if is_active else DIM_INACTIVE
        label = f"•   {name}:" if is_active else f"    {name}:"
        if recede:
            label = _dim(label, recede)
        lines.append(label)
        lines.append(f"    {make_shimmer_bar(frame_index, spinner)}")
        if detail:
            lines.append("    " + _dim(detail, recede if recede else DIM_RESET))
        lines.append("")
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
        return True if pending is None else (p.get("_dir") in pending)

    if latest_data:
        blocks = []
        for p in latest_data:
            if _is_pending(p):
                block = format_loading_provider_block(
                    p, frame, selected_dir, selected_idx, selected_metric
                )
            else:
                block = format_provider_block(
                    p, selected_dir, selected_idx, selected_metric
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
    text = get_selected_metric_text(
        latest_data, selected, spinner=(spinner if selected_pending else None)
    )

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
                p, selected_dir, selected_idx, selected_metric
            )
            if block:
                blocks.append(block)
        tooltip = f"{header}{sep}\n" + "\n".join(blocks)
    else:
        tooltip = f"{header}\n\n{'─' * BAR_LINE_WIDTH}"

    metric_text = get_selected_metric_text(latest_data, selected)
    return {"text": metric_text, "tooltip": tooltip.strip()}
