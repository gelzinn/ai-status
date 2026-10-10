"""Structured snapshots for the Omarchy plugin; no Waybar/Pango side effects."""

import json
import math
import os
import threading
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from . import about, config, fetch, paths, render, state, reset_credits


class _PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value):
    parser = _PlainText()
    parser.feed(str(value or ""))
    parser.close()
    return "".join(parser.parts)


class LogoCache:
    """Cache original images asynchronously so logo downloads never block usage."""

    def __init__(self):
        self.directory = Path.home() / ".cache/ai-status/quickshell-logos"
        metadata = Path(__file__).resolve().parents[3] / "shared/providers/providers.json"
        try:
            self.providers = json.loads(metadata.read_text())
        except (OSError, ValueError):
            self.providers = {}
        self.paths = {}
        self.attempts = {}

    def get(self, provider):
        url = self.providers.get(provider, {}).get("logo")
        if not url:
            return ""
        # SVG is detected by content, since favicon URLs often have no suffix.
        for extension in ("svg", "png", "jpg", "webp", "gif"):
            path = self.directory / f"{provider}.{extension}"
            if path.is_file() and path.stat().st_size:
                return str(path)
        if provider not in self.attempts or time.monotonic() - self.attempts[provider] > 300:
            self.attempts[provider] = time.monotonic()
            threading.Thread(target=self._download, args=(provider, url), daemon=True).start()
        return self.paths.get(provider, "")

    def _download(self, provider, url):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "ai-status"})
            with urllib.request.urlopen(request, timeout=5) as response:
                data = response.read(2 * 1024 * 1024)
            if not data:
                return
            suffix = Path(urlparse(url).path).suffix.lstrip(".").lower()
            extension = "svg" if b"<svg" in data[:1024] else suffix
            if extension not in ("svg", "png", "jpg", "webp", "gif"):
                extension = "png"
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{provider}.{extension}"
            temporary = path.with_suffix(f".{os.getpid()}.tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
            self.paths[provider] = str(path)
        except (OSError, ValueError):
            pass  # The widget still works with text when a logo is unavailable.


def settings_snapshot(selected):
    available = config.available_providers()
    enabled = [name for name in config.enabled_order() if name in available]
    providers = paths.read_json(paths.LIB_DIR.parent / "shared/providers/providers.json")
    return {
        "available": available,
        "names": {name: providers.get(name, {}).get("name", name) for name in available},
        "order": enabled + [name for name in available if name not in enabled],
        "enabled": enabled,
        "display": {key: selected.get(key, default) for key, default in (
            ("show_provider", True), ("show_model", True),
            ("show_metric", False), ("show_pct", True),
        )},
        "iconMode": state.get_icon_mode(selected),
    }


def save_settings(payload):
    """Validate a native form before publishing shared preferences atomically."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid settings")
    available = config.available_providers()
    enabled = payload.get("enabled")
    if (not isinstance(enabled, list) or not enabled
            or any(not isinstance(name, str) or name not in available for name in enabled)
            or len(set(enabled)) != len(enabled)):
        raise ValueError("Enable at least one available provider, without duplicates")
    display = payload.get("display")
    fields = ("show_provider", "show_model", "show_metric", "show_pct")
    if not isinstance(display, dict) or any(type(display.get(key)) is not bool for key in fields):
        raise ValueError("Invalid display settings")
    if not any(display[key] for key in fields):
        raise ValueError("Show at least one text field in the bar")
    icon_mode = payload.get("iconMode")
    if icon_mode not in state.ICON_MODES:
        raise ValueError("Invalid provider icon")
    choice = payload.get("selected")
    if (not isinstance(choice, dict) or choice.get("provider") not in enabled
            or type(choice.get("idx")) is not int or choice["idx"] < 0
            or not isinstance(choice.get("metric"), str) or not choice["metric"]):
        raise ValueError("Choose an enabled provider and limit")
    selected = dict(state.load_selected() or {})
    selected.update({key: choice[key] for key in ("provider", "idx", "metric")})
    selected.update({key: display[key] for key in fields}, icon_mode=icon_mode)
    # Report I/O errors to the form instead of using the best-effort wrappers.
    state._save_json(config.CONFIG_FILE, enabled)
    state._save_json(state.SELECTED_FILE, selected)
    state.trigger_refresh()


def usable_metrics(entry):
    """Keep genuine zero usage and cached successes, but omit error placeholders."""
    if fetch._is_error_result(entry):
        return []
    metrics = []
    for metric in entry.get("metrics", []):
        try:
            percentage = float(metric["percentage"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(percentage):
            metrics.append(metric)
    return metrics


def select_metric(selection):
    if not isinstance(selection, dict):
        raise ValueError("Invalid metric selection")
    provider, idx, key = selection.get("provider"), selection.get("idx"), selection.get("metric")
    if (not isinstance(provider, str) or type(idx) is not int or idx < 0
            or not isinstance(key, str) or not key):
        raise ValueError("Invalid metric selection")
    for entry in state.load_cache():
        if entry.get("_dir") == provider and entry.get("_idx", 0) == idx and provider in config.enabled_order():
            if key in [render.metric_key(metric) for metric in usable_metrics(entry)]:
                selected = state.load_selected() or {}
                selected.update(provider=provider, idx=idx, metric=key)
                state.save_selected(selected)
                return
    raise ValueError("This usage metric is no longer available")


def build_snapshot(data, selected=None, pending=None, logo_path="", logo_paths=None):
    selected = dict(selected or {})
    pending = set(pending or ())
    logo_paths = logo_paths or {}
    order = config.enabled_order()
    providers = []
    for name in order:
        entries = [p for p in data if p.get("_dir") == name]
        for entry in entries:
            metrics = []
            for metric in sorted(usable_metrics(entry), key=lambda m: render.TYPE_ORDER.get(m.get("type"), 4)):
                percentage = float(metric["percentage"])
                detail = metric.get("detail")
                if detail is None:
                    detail = render.format_reset_time(metric.get("reset_in_seconds"), metric.get("type"))
                metrics.append({
                    "key": render.metric_key(metric),
                    "type": metric.get("type", "generic"),
                    "name": render.TYPE_NAMES.get(metric.get("type"), "Usage"),
                    "percentage": percentage,
                    "resetInSeconds": metric.get("reset_in_seconds"),
                    "detail": plain_text(detail),
                })
            if not metrics:
                continue
            providers.append({
                "id": name,
                "idx": entry.get("_idx", 0),
                "name": entry.get("provider", name),
                "logoPath": logo_paths.get(name, ""),
                "loading": name in pending,
                "cached": bool(entry.get("_cached")),
                "error": plain_text(entry.get("_error") or ("No usage data available" if not metrics and name not in pending else "")),
                "metrics": metrics,
                "resetCredits": reset_credits.presentation(entry.get("reset_credits")),
            })
    current = next((p for p in providers if p["id"] == selected.get("provider") and p["idx"] == selected.get("idx", 0)), None)
    if current is None and providers:
        current = providers[0]
        selected.update(provider=current["id"], idx=current["idx"])
    if current and current["metrics"] and selected.get("metric") not in [m["key"] for m in current["metrics"]]:
        selected["metric"] = current["metrics"][0]["key"]
    selected_loading = selected.get("provider") in pending
    enabled_data = [dict(p, metrics=usable_metrics(p)) for p in data if p.get("_dir") in order and usable_metrics(p)]
    text = render.get_selected_metric_text(enabled_data, selected, spinner="…" if selected_loading else None)
    if not current:
        text = "AI Status …" if pending else "AI Status"
        logo_path = ""
    elif state.get_icon_mode(selected) == "logo":
        logo_path = logo_paths.get(current["id"], logo_path)
    return {
        "schemaVersion": 1,
        "about": about.project_info(),
        "version": fetch.get_version_info(),
        "text": text,
        "selected": selected,
        "iconMode": state.get_icon_mode(selected),
        "logoPath": logo_path,
        "loading": bool(pending),
        "providers": providers,
        "settings": settings_snapshot(selected),
    }
