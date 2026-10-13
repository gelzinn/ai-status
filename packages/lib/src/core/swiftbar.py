"""SwiftBar compatibility renderer using the shared native desktop model."""
import base64
from functools import lru_cache
import json
import os
import sys

from . import config, macos, quickshell, render, state
from .swiftbar_frames import spark_frame, LOGO  # noqa: F401 (compatibility export)

DIM = "#8e8e93,#98989d"
FAINT = "#aeaeb2,#8e8e93"
BAR_FONT = "Menlo"
BAR_WIDTH = 16
SPINNERS = render.SPINNERS


def binary_path():
    installed = os.path.expanduser("~/.local/bin/ai-status")
    if os.path.exists(installed):
        return installed
    return os.path.realpath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "ai-status"))


def _plain(text):
    # SwiftBar's text protocol reserves |, newlines and leading -- for menus.
    return quickshell.plain_text(text).replace("|", "¦").replace("\r", " ").replace("\n", " ").replace("\t", " ").replace("\x00", "").lstrip("-")


def _quote(value):
    return json.dumps(str(value), ensure_ascii=False)


def _line(text, *params):
    return _plain(text) + (" | " + " ".join(params) if params else "")


def _action(command, *arguments, terminal=False):
    # Use the known interpreter instead of relying on SwiftBar's minimal PATH.
    values = [binary_path(), command, *arguments]
    return [f"bash={_quote(sys.executable)}", *[f"param{i}={_quote(value)}" for i, value in enumerate(values, 1)],
            f"terminal={str(terminal).lower()}", "refresh=true"]


def _bar(percentage, width=BAR_WIDTH):
    filled = int(round(width * max(0, min(100, float(percentage))) / 100))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


@lru_cache(maxsize=16)
def _image(path):
    try:
        with open(path, "rb") as source:
            return base64.b64encode(source.read()).decode("ascii")
    except OSError:
        return ""


def _snapshot(cache, selected, spinner=None):
    connections = config.enabled_connections()
    logos = macos.LogoCache()
    paths = {entry["provider"]: logos.get(entry["provider"]) for entry in connections}
    pending = [entry["connection_id"] for entry in connections] if spinner else ()
    return quickshell.build_snapshot(cache, selected, pending=pending, logo_paths=paths)


def title_text(cache, selected, spinner=None):
    snapshot = _snapshot(cache, selected, spinner)
    text = snapshot["text"].replace("\U000f06a9", "").strip()
    if spinner:
        text = text.replace("…", spinner)
    return _plain(text) or "AI Status"


def render_menu(cache, selected, spinner=None, title_image=None):
    snapshot = _snapshot(cache, selected, spinner)
    bar_items = snapshot.get("barItems", [])
    title = snapshot["text"].replace("\U000f06a9", "").strip().replace("…", spinner or "…")
    title_params = []
    if title_image:
        title_params.append(f"templateImage={title_image}")
    elif snapshot["iconMode"] == "logo" and snapshot["logoPath"]:
        title_params.append(f"image={_image(snapshot['logoPath'])}")
    elif snapshot["iconMode"] == "bot":
        path = macos.paths.LIB_DIR / "assets" / "app.png"
        title_params.append(f"image={_image(str(path))}")
    out = [_line(title or "AI Status", *title_params), "---",
           _line(f"AI Status · v{snapshot['about']['version']}", "size=11", f"color={DIM}"), "---"]
    if snapshot["version"]["has_update"]:
        guide = snapshot["update"]
        out.append(_line(f"Update available: v{snapshot['version']['latest']} →", "color=#89b4fa",
                         f"href={guide['guideUrl']}"))
        if guide["canUpdate"]:
            out.append("--" + _line(guide["actionLabel"], *_action("update")))
        out.append("--" + _line("Update guide", f"href={guide['guideUrl']}"))
        out.append("--" + _line("Release notes", f"href={guide['releaseUrl']}"))
        out.append("---")
    if not snapshot["providers"]:
        out.append(_line("Checking your connected providers…" if spinner else "No usage available. Connect a provider and refresh.", f"color={DIM}"))
    for index, provider in enumerate(snapshot["providers"]):
        if index:
            out.append("---")
        active = any(item["provider"] == provider["id"] and item["idx"] == provider["idx"] for item in bar_items)
        select = (provider["id"], str(provider["idx"]))
        first = provider["metrics"][0]["key"]
        params = ["size=14", *_action("swiftbar-select", *select, first)]
        if provider["logoPath"]:
            params.append(f"image={_image(provider['logoPath'])}")
        if not active:
            params.append(f"color={DIM}")
        out.append(_line(("→ " if active else "") + provider["name"], *params))
        if provider["cached"]:
            out.append(_line("Cached data", "size=11", f"color={FAINT}"))
        if provider["error"]:
            out.append(_line(provider["error"], "size=11", f"color={FAINT}"))
        for metric in provider["metrics"]:
            checked = any(item["provider"] == provider["id"] and item["idx"] == provider["idx"] and item["metric"] == metric["key"] for item in bar_items)
            params = [f"font={BAR_FONT}", "size=13", *_action("swiftbar-select", *select, metric["key"])]
            params.append("checked=true" if checked else f"color={DIM}")
            value = metric["value"]
            bar = f"{_bar(metric['percentage'])}  " if metric["hasPercentage"] else ""
            out.append(_line(f"{metric['name']}:  {bar}{value}", *params))
            if metric["detail"]:
                out.append(_line(metric["detail"], "size=11", f"color={FAINT}"))
        credits = provider.get("resetCredits")
        if credits:
            out.append(_line(f"Reset credits: {credits['available']} available", f"color={DIM}"))
            for row in credits["rows"]:
                detail = f"{row['title']} · {row['count']} · {row['expires']} {row['timezone']}"
                out.append("--" + _line(detail, "size=11"))
                if row["remaining"]:
                    out.append("--" + _line(row["remaining"], "size=11", f"color={FAINT}"))
    out.extend(["---", _line("Refresh", *_action("swiftbar-refresh")),
                _line("Cycle metric", *_action("cycle-metric", "--frontend", "swiftbar")),
                _line("Settings", *_action("config", "--frontend", "swiftbar", terminal=True)),
                _line("About AI Status", f"href={snapshot['about']['github']}", "size=11", f"color={DIM}")])
    return "\n".join(out)


def render_from_state(spinner=None):
    return render_menu(state.load_cache(), state.load_selected(), spinner=spinner)
