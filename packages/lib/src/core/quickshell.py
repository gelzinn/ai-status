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

from . import config, fetch, render, state


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


def build_snapshot(data, selected=None, pending=None, logo_path=""):
    selected = dict(selected or {})
    pending = set(pending or ())
    order = config.enabled_order()
    providers = []
    for name in order:
        entries = [p for p in data if p.get("_dir") == name]
        if not entries:
            entries = [{"_dir": name, "_idx": 0, "provider": name, "metrics": []}]
        for entry in entries:
            metrics = []
            for metric in sorted(entry.get("metrics", []), key=lambda m: render.TYPE_ORDER.get(m.get("type"), 4)):
                try:
                    percentage = float(metric.get("percentage", 0))
                except (TypeError, ValueError):
                    percentage = 0.0
                if not math.isfinite(percentage):
                    percentage = 0.0
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
            providers.append({
                "id": name,
                "idx": entry.get("_idx", 0),
                "name": entry.get("provider", name),
                "loading": name in pending,
                "cached": bool(entry.get("_cached")),
                "error": plain_text(entry.get("_error") or ("No usage data available" if not metrics and name not in pending else "")),
                "metrics": metrics,
            })
    current = next((p for p in providers if p["id"] == selected.get("provider") and p["idx"] == selected.get("idx", 0)), None)
    if current is None and providers:
        current = next((p for p in providers if p["metrics"]), providers[0])
        selected.update(provider=current["id"], idx=current["idx"])
    if current and current["metrics"] and selected.get("metric") not in [m["key"] for m in current["metrics"]]:
        selected["metric"] = current["metrics"][0]["key"]
    selected_loading = selected.get("provider") in pending
    enabled_data = [p for p in data if p.get("_dir") in order]
    text = render.get_selected_metric_text(enabled_data, selected, spinner="…" if selected_loading else None)
    if current and not current["metrics"]:
        text = (render.ICON + " " if state.get_icon_mode(selected) == "bot" else "") + current["name"] + (" …" if selected_loading else " unavailable")
    elif not current:
        text = "AI Status"
    return {
        "schemaVersion": 1,
        "version": fetch.get_version_info(),
        "text": text,
        "selected": selected,
        "iconMode": state.get_icon_mode(selected),
        "logoPath": logo_path,
        "loading": bool(pending),
        "providers": providers,
    }
