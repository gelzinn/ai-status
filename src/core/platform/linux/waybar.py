from ... import fetch
from ... import types as _types

SPINNERS = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
BAR_LINE_WIDTH = 34
_BAR_WIDTH = 25

ICON = "\U000F06A9"

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

def get_selected_metric_text(latest_data, selected):
    p = _find_selected_provider(latest_data, selected)
    if not p:
        return ICON
    provider_name = p.get("provider", "")
    metric_type = selected.get("metric", "rolling")
    metrics = p.get("metrics", [])
    for m in metrics:
        if m.get("type") == metric_type:
            pct = float(m.get("percentage", 0.0))
            return f"{ICON}\u2003{provider_name} {pct:.0f}%"
    if metrics:
        pct = float(metrics[0].get("percentage", 0.0))
        return f"{ICON}\u2003{provider_name} {pct:.0f}%"
    return f"{ICON}\u2003{provider_name}"

def get_selected_provider_name(latest_data, selected):
    p = _find_selected_provider(latest_data, selected)
    if not p:
        return ICON
    return f"{ICON}\u2003{p.get('provider', '')}"


def format_reset_time(seconds, mtype):
    if seconds is None:
        return "<span alpha='50%'>no reset available</span>"
    
    seconds = max(0, int(seconds))
    if seconds == 0: return "Resets now"
        
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    
    if days > 0: return f"Resets in {days}d {hours}h"
    if hours > 0: return f"Resets in {hours}h {minutes}m"
    return f"Resets in {minutes}m"

def format_provider_block(provider_data, selected_dir=None, selected_idx=None, selected_metric=None):
    provider = provider_data.get("provider", "AI Provider")
    metrics = provider_data.get("metrics", [])
    if not metrics: return ""

    is_selected = provider_data.get("_dir") == selected_dir and provider_data.get("_idx") == selected_idx
    prefix = "→ " if is_selected else "  "
    line = f"{prefix}{provider}"
    if provider_data.get("_error"):
        err_icon = '<span foreground="#ef4444"> ●</span>'
        pad = max(1, BAR_LINE_WIDTH - len(prefix) - len(provider) - 2)
        line = f"{prefix}{provider}{' ' * pad}{err_icon}"
    sorted_metrics = sorted(metrics, key=lambda m: _types.TYPE_ORDER.get(m.get("type", "generic"), 4))
    lines = [line, ""]
    for metric in sorted_metrics:
        mtype = metric.get("type", "generic")
        name = _types.TYPE_NAMES.get(mtype, "Usage")
        is_active = is_selected and mtype == selected_metric
        pct = float(metric.get("percentage", 0.0))
        seconds = metric.get("reset_in_seconds")
        detail = metric.get("detail")
        if detail is None: detail = format_reset_time(seconds, mtype)

        if is_active:
            lines.append(f"•   {name}:")
        else:
            lines.append(f"    {name}:")
        lines.append(f"    {_types.make_progress_bar(pct, width=_BAR_WIDTH, markup=True)}")
        if detail: lines.append(f"    {detail}")
        lines.append("")
    return "\n".join(lines)

def format_loading_provider_block(provider_data, frame_index):
    provider = provider_data.get("provider", "AI Provider")
    metrics = provider_data.get("metrics", [])
    if not metrics: return ""
        
    sorted_metrics = sorted(metrics, key=lambda m: _types.TYPE_ORDER.get(m.get("type", "generic"), 4))
    spinner = SPINNERS[frame_index % len(SPINNERS)]
    line = f"{provider} {spinner}"
    if provider_data.get("_error"):
        err_icon = '<span foreground="#ef4444"> ●</span>'
        pad = max(1, BAR_LINE_WIDTH - len(provider) - len(spinner) - 3)
        line = f"{provider} {spinner}{' ' * pad}{err_icon}"
    lines = [line, ""]
    for metric in sorted_metrics:
        mtype = metric.get("type", "generic")
        name = _types.TYPE_NAMES.get(mtype, "Usage")
        pct = float(metric.get("percentage", 0.0))
        seconds = metric.get("reset_in_seconds")
        detail = metric.get("detail")
        if detail is None: detail = format_reset_time(seconds, mtype)
            
        lines.append(f"  {name}:")
        lines.append(f"  {_types.make_loading_bar(pct, frame_index, width=_BAR_WIDTH, markup=True)}")
        if detail: lines.append(f"  {detail}")
        lines.append("")
    return "\n".join(lines)

def format_header():
    info = fetch.get_version_info()
    name = "Omarchy AI Status"
    version = f"v{info['current']}"
    padding = BAR_LINE_WIDTH - len(name) - len(version)
    if padding < 1:
        padding = 1
    line = f"{name}{' ' * padding}{version}"
    if info['has_update']:
        line += f"\n<span alpha='70%'>Update available: v{info['latest']}</span>"
    return line

def build_loading_state(latest_data, frame, selected=None):
    spinner = SPINNERS[frame % len(SPINNERS)]
    header = format_header()
    sep = f"\n\n{'─' * BAR_LINE_WIDTH}\n"
    if latest_data:
        blocks = []
        for p in latest_data:
            block = format_loading_provider_block(p, frame)
            if block: blocks.append(block)
        tooltip = f"{header}{sep}\n" + "\n".join(blocks)
    else:
        bar = _types.make_empty_loading_bar(frame, width=_BAR_WIDTH, markup=True)
        tooltip = f"{header}\n\n{'─' * BAR_LINE_WIDTH}\n\n  Loading AI Provider Status {spinner}\n  {bar}"

    provider_text = get_selected_provider_name(latest_data, selected)
    return {
        "text": f"{provider_text} {spinner}" if provider_text != ICON else f"{ICON} {spinner}",
        "tooltip": tooltip.strip()
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
            block = format_provider_block(p, selected_dir, selected_idx, selected_metric)
            if block: blocks.append(block)
        tooltip = f"{header}{sep}\n" + "\n".join(blocks)
    else:
        tooltip = f"{header}\n\n{'─' * BAR_LINE_WIDTH}"

    metric_text = get_selected_metric_text(latest_data, selected)
    return {
        "text": metric_text,
        "tooltip": tooltip.strip()
    }
