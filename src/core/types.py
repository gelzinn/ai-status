TYPE_NAMES = {
    "rolling": "Rolling Usage",
    "daily": "Daily Usage",
    "weekly": "Weekly Usage",
    "monthly": "Monthly Usage",
    "generic": "Usage",
}

TYPE_ORDER = {k: i for i, k in enumerate(TYPE_NAMES)}

METRIC_CYCLE = [t for t in TYPE_ORDER if t not in ("daily", "generic")]

PROGRESS_WIDTH = 20
_FILL = "█"
_EMPTY = "░"

def _empty_span(alpha):
    return f"<span alpha='{alpha}%'>█</span>"

def make_progress_bar(pct, width=PROGRESS_WIDTH, markup=False):
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100))
    empty = width - filled
    if markup:
        bar = _FILL * filled + _empty_span(15) * empty if empty else _FILL * filled
        return f"[{bar}] {pct:.0f}%"
    return f"{_FILL * filled}{_EMPTY * empty} {pct:.0f}%"

def make_loading_bar(pct, frame, width=PROGRESS_WIDTH, markup=False):
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100))
    sweep = filled if filled > 0 else width
    center = frame % (sweep + 6) - 3
    chars = []
    for i in range(width):
        if markup:
            if i < filled:
                d = abs(i - center)
                a = "100" if d == 0 else "85" if d == 1 else "60" if d == 2 else "40"
                chars.append(f"<span alpha='{a}%'>█</span>")
            else:
                if filled == 0:
                    d = abs(i - center)
                    a = "80" if d == 0 else "50" if d == 1 else "30" if d == 2 else "15"
                else:
                    a = "15"
                chars.append(f"<span alpha='{a}%'>█</span>")
        else:
            chars.append(_FILL if i < filled else _EMPTY)
    bar = "".join(chars)
    if markup:
        return f"[{bar}] {pct:.0f}%"
    return f"{bar} {pct:.0f}%"

def make_empty_loading_bar(frame, width=PROGRESS_WIDTH, markup=False):
    pos = frame % (2 * (width - 4))
    if pos >= width - 4:
        pos = (width - 4) - (pos - (width - 4))
    chars = []
    for i in range(width):
        if markup:
            d = abs(i - (pos + 1))
            a = "90" if d == 0 else "65" if d == 1 else "40" if d == 2 else "25" if d == 3 else "12"
            chars.append(f"<span alpha='{a}%'>█</span>")
        else:
            chars.append(_FILL if i == pos else _EMPTY)
    bar = "".join(chars)
    if markup:
        return f"[{bar}] Loading..."
    return f"{bar} Loading..."
