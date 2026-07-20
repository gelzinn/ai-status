"""SwiftBar / xbar plugin renderer (macOS menu bar).

The Linux side runs a persistent Waybar daemon that streams JSON with Pango
markup. macOS has no Waybar; the equivalent is **SwiftBar** -- a menu-bar host
that runs a plugin script on an interval (or as a long-lived *streamable*
process) and renders its stdout.

This module turns the same cached provider data (``state.load_cache()``, the
list produced by ``fetch.fetch_all_data``) into SwiftBar's plain-text menu
format. SwiftBar does **not** parse Pango, so every ``<span alpha=...>`` from
``render.py`` is dropped here; emphasis comes from SwiftBar's own ``color=`` /
``size=`` params, a native checkmark on the active metric, and plain Unicode
block bars.

Output shape::

    Claude 62%                      <- menu bar title (line 1, before the ---)
    ---
    AI Status . v0.9.0
    ---
    -> Claude
    Rolling Usage  [##########......]  62%   (checked when active)
    Resets in 2h 13m
    ...
    ---
    Refresh    | bash=<abs> param1=swiftbar-refresh terminal=false refresh=true
    Settings   | bash=<abs> param1=config terminal=true

Every ``bash=`` target is an **absolute** path: SwiftBar runs plugins with a
minimal ``PATH`` where a bare ``ai-status`` would not resolve.
"""

import os

from . import render
from . import state
from .swiftbar_frames import spark_frame, LOGO  # noqa: F401 (re-exported)


# ── colors ────────────────────────────────────────────────────────────────
# SwiftBar accepts a "light,dark" pair so the menu reads in both appearances.
# Selected / active rows omit color so they inherit the system label color.
DIM = "#8e8e93,#98989d"      # secondary text (system gray, both appearances)
FAINT = "#aeaeb2,#8e8e93"    # tertiary text (reset timers)
RED = "#ff3b30,#ff453a"      # stale / error indicator
ACCENT = "#d97757,#e08a6a"   # selected provider arrow (Claude terracotta)

# Monospace so the block bars line up column-for-column in the dropdown.
BAR_FONT = "Menlo"
BAR_WIDTH = 16

FILLED = "█"  # full block
EMPTY = "░"   # light shade

SPINNERS = render.SPINNERS


def binary_path():
    """Absolute path to the ``ai-status`` entry point for ``bash=`` actions.

    Prefer the installed symlink (``~/.local/bin/ai-status``); fall back to this
    checkout's own ``src/bin/ai-status`` so the plugin works from a dev tree too.
    """
    installed = os.path.expanduser("~/.local/bin/ai-status")
    if os.path.exists(installed):
        return installed
    return os.path.realpath(
        os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bin",
            "ai-status",
        )
    )


def _bar(percentage, width=BAR_WIDTH):
    percentage = max(0.0, min(100.0, float(percentage)))
    filled = int(round(width * percentage / 100))
    return f"[{FILLED * filled}{EMPTY * (width - filled)}]"


def _reset_text(seconds):
    if seconds is None:
        return None
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


def _params(*parts):
    """Join `key=value` params into the trailing `| ...` of a SwiftBar line."""
    return " | " + " ".join(parts) if parts else ""


def _line(text, *params):
    return f"{text}{_params(*params)}"


def _split_name(full):
    """"Antigravity (Gemini)" -> ("Antigravity", "Gemini")."""
    name, model = full, ""
    if "(" in full and full.rstrip().endswith(")"):
        head, _, tail = full.partition("(")
        name = head.strip()
        model = tail.rstrip(")").strip()
    return name, model


def title_text(cache, selected, spinner=None):
    """Menu-bar title: selected provider + percentage, honoring display flags.

    ``spinner`` (a glyph) replaces the percentage while a refresh is in flight.
    """
    selected = selected or {}
    p = render._find_selected_provider(cache, selected)
    if not p:
        return spinner or "AI Status"

    name, model = _split_name(p.get("provider", ""))
    metrics = p.get("metrics", [])
    key = selected.get("metric", "rolling")
    metric = next((m for m in metrics if render.metric_key(m) == key), None)
    if metric is None and metrics:
        metric = metrics[0]

    show_provider = selected.get("show_provider", True)
    show_model = selected.get("show_model", True)
    show_metric = selected.get("show_metric", False)
    show_pct = selected.get("show_pct", True)
    if not (show_provider or show_model or show_metric or show_pct):
        show_provider = show_pct = True

    parts = []
    if show_provider and name:
        parts.append(name)
    if show_model and model:
        parts.append(f"({model})" if show_provider else model)
    if show_metric and metric:
        parts.append(render.TYPE_NAMES.get(metric.get("type", "generic"), "Usage"))
    if show_pct:
        if spinner is not None:
            parts.append(spinner)
        elif metric is not None:
            parts.append(f"{float(metric.get('percentage', 0.0)):.0f}%")
        else:
            parts.append("0%")
    elif spinner is not None:
        parts.append(spinner)

    return " ".join(parts) or (spinner or "AI Status")


def _provider_block(p, selected):
    """The dropdown lines for one provider (header + metric rows)."""
    selected = selected or {}
    metrics = p.get("metrics", [])
    if not metrics:
        return []

    dir_name = p.get("_dir")
    idx = p.get("_idx", 0)
    is_selected = dir_name == selected.get("provider") and idx == selected.get("idx", 0)
    selected_metric = selected.get("metric")

    bin_path = binary_path()
    select_action = [
        f"bash={bin_path}",
        "param1=swiftbar-select",
        f"param2={dir_name}",   # dir names are space-free — no quoting needed
        f"param3={idx}",
        "terminal=false",
        "refresh=true",
    ]

    lines = []
    provider = p.get("provider", "AI Provider")
    header = f"→ {provider}" if is_selected else provider
    header_params = ["size=14", *select_action]
    header_params.append(f"color={ACCENT}" if is_selected else f"color={DIM}")
    lines.append(_line(header, *header_params))
    if p.get("_error"):
        lines.append(_line(f"● stale . {p['_error']}", "size=11", f"color={RED}"))

    sorted_metrics = sorted(
        metrics, key=lambda m: render.TYPE_ORDER.get(m.get("type", "generic"), 4)
    )
    for metric in sorted_metrics:
        mtype = metric.get("type", "generic")
        name = render.TYPE_NAMES.get(mtype, "Usage")
        pct = float(metric.get("percentage", 0.0))
        is_active = is_selected and render.metric_key(metric) == selected_metric
        # `checked=true` draws a native macOS checkmark on the active metric --
        # aligned by SwiftBar, so it survives whitespace trimming (a manual
        # leading bullet would not).
        row = f"{name}  {_bar(pct)}  {pct:.0f}%"
        row_params = [
            f"font={BAR_FONT}",
            "size=13",
            *select_action,
            f'param4="{render.metric_key(metric)}"',
        ]
        if is_active:
            row_params.append("checked=true")
        else:
            row_params.append(f"color={DIM}")
        lines.append(_line(row, *row_params))

        detail = metric.get("detail")
        if detail is None:
            detail = _reset_text(metric.get("reset_in_seconds"))
        if detail:
            lines.append(_line(detail, "size=11", f"color={FAINT}"))
    return lines


def render_menu(cache, selected, spinner=None, title_image=None):
    """Full SwiftBar plugin output for the current cache + selection.

    ``spinner`` animates the menu-bar title text and ``title_image`` (a base64
    PNG) sets the menu-bar icon — both used by the streamable plugin to play the
    Claude spark while refreshing. The dropdown always shows the last known
    values from the cache.
    """
    from . import __version__

    bin_path = binary_path()
    title_params = []
    if title_image:
        # templateImage: macOS tints the alpha mask to the menu-bar color.
        title_params.append(f"templateImage={title_image}")
    out = [_line(title_text(cache, selected, spinner=spinner), *title_params)]
    out.append("---")
    out.append(_line(f"AI Status · v{__version__}", "size=11", f"color={DIM}"))
    out.append("---")

    if not cache:
        out.append(_line("No data yet", "size=12", f"color={DIM}"))
        out.append(_line("Fetching provider usage...", "size=11", f"color={FAINT}"))
    else:
        first = True
        for p in cache:
            block = _provider_block(p, selected)
            if not block:
                continue
            if not first:
                out.append("---")
            out.extend(block)
            first = False

    out.append("---")
    out.append(_line("↻ Refresh", f"bash={bin_path}", "param1=swiftbar-refresh",
                     "terminal=false", "refresh=true"))
    out.append(_line("⋯ Cycle metric", f"bash={bin_path}", "param1=cycle-metric",
                     "terminal=false", "refresh=true"))
    out.append(_line("⚙ Settings", f"bash={bin_path}", "param1=config", "terminal=true"))
    out.append(_line("About ai-status", "href=https://github.com/gelzinn/ai-status",
                     "size=11", f"color={DIM}"))
    return "\n".join(out)


def render_from_state(spinner=None):
    """Convenience: read cache + selection from disk and render."""
    return render_menu(state.load_cache(), state.load_selected(), spinner=spinner)
