"""Structured snapshots for the Omarchy plugin; no Waybar/Pango side effects."""

import json
import os
import threading
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from . import about, config, fetch, logos, paths, render, state, reset_credits, reset_actions, updates, notifications, usage_credits


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
        bundled = logos.contrast_logo(provider)
        if bundled:
            return bundled
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
    available = config.available_connections()
    enabled = [name for name in config.enabled_connection_order() if name in available]
    providers = paths.read_json(paths.LIB_DIR.parent / "shared/providers/providers.json")
    return {
        "available": available,
        "names": {name: (providers.get(config.connection_info(name)["provider"], {}).get("name", name)
                         + (" · " + config.connection_info(name)["label"] if name.startswith("account:") else "")) for name in available},
        "providerIds": {name: config.connection_info(name)["provider"] for name in available},
        "order": enabled + [name for name in available if name not in enabled],
        "enabled": enabled,
        "display": {key: selected.get(key, default) for key, default in (
            ("show_provider", True), ("show_model", True),
            ("show_metric", False), ("show_pct", True),
        )},
        "iconMode": state.get_icon_mode(selected),
        "usageDisplay": state.get_usage_display(selected),
        "items": state.get_selected_items(selected),
        "refreshIntervalMinutes": state.get_refresh_interval_minutes(selected),
        "notifications": notifications.load_settings(),
    }


def save_settings(payload):
    """Validate a native form before publishing shared preferences atomically."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid settings")
    available = config.available_connections()
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
    selected = dict(state.load_selected() or {})
    previous = dict(selected)

    def valid_choice(choice):
        return (isinstance(choice, dict) and isinstance(choice.get("provider"), str)
                and choice["provider"] in enabled and type(choice.get("idx")) is int and choice["idx"] >= 0
                and isinstance(choice.get("metric"), str) and bool(choice["metric"]))

    if "items" in payload:
        items = payload["items"]
        if (not isinstance(items, list) or not items or not all(valid_choice(choice) for choice in items)
                or len(state.get_selected_items({"items": items})) != len(items)):
            raise ValueError("Choose at least one enabled provider and limit, without duplicates")
        state.set_selected_items(selected, state.order_bar_items(items, enabled))
    else:
        choice = payload.get("selected")
        if not valid_choice(choice):
            raise ValueError("Choose an enabled provider and limit")
        state.select_primary(selected, choice)
        state.set_selected_items(selected, state.order_bar_items(
            [item for item in state.get_selected_items(selected) if item["provider"] in enabled], enabled))
    usage_display = payload.get("usageDisplay", state.get_usage_display(selected))
    if usage_display not in state.USAGE_DISPLAY_MODES:
        raise ValueError("Invalid usage display")
    refresh_interval = state.validate_refresh_interval_minutes(payload.get(
        "refreshIntervalMinutes", state.get_refresh_interval_minutes(selected)))
    alert_settings = notifications.validate_settings(payload["notifications"]) if "notifications" in payload else None
    refresh_only = (
        enabled == config.enabled_connection_order()
        and state.get_selected_items(selected) == state.get_selected_items(previous)
        and display == {key: previous.get(key, default) for key, default in (
            ("show_provider", True), ("show_model", True), ("show_metric", False), ("show_pct", True))}
        and icon_mode == state.get_icon_mode(previous)
        and usage_display == state.get_usage_display(previous)
        and (alert_settings is None or alert_settings == notifications.load_settings())
    )
    selected.update({key: display[key] for key in fields}, icon_mode=icon_mode, usage_display=usage_display,
                    refresh_interval_minutes=refresh_interval)
    # Report I/O errors to the form instead of using the best-effort wrappers.
    if not refresh_only:
        if alert_settings is not None:
            notifications.save_settings(alert_settings)
        config.save_connection_order(enabled)
    state._save_json(state.SELECTED_FILE, selected)
    if not refresh_only:
        state.trigger_refresh()


def usable_metrics(entry):
    """Keep genuine zero usage and cached successes, but omit error placeholders."""
    return render.usable_metrics(entry)


def select_metric(selection):
    if not isinstance(selection, dict):
        raise ValueError("Invalid metric selection")
    provider, idx, key = selection.get("provider"), selection.get("idx"), selection.get("metric")
    if (not isinstance(provider, str) or type(idx) is not int or idx < 0
            or not isinstance(key, str) or not key):
        raise ValueError("Invalid metric selection")
    selected = state.load_selected() or {}
    for entry in state.load_cache():
        if render.connection_key(entry) == provider and entry.get("_idx", 0) == idx and provider in config.enabled_connection_order():
            if key in [render.metric_key(metric) for metric in usable_metrics(entry)]:
                if not state.can_select_metric(selected):
                    return
                state.select_primary(selected, {"provider": provider, "idx": idx, "metric": key},
                                     provider_order=config.enabled_connection_order())
                state.save_selected(selected)
                return
    raise ValueError("This usage metric is no longer available")


def build_snapshot(data, selected=None, pending=None, logo_path="", logo_paths=None):
    selected = dict(selected or {})
    preferences = dict(selected)
    pending = set(pending or ())
    logo_paths = logo_paths or {}
    order = config.enabled_connection_order()
    providers = []
    for name in order:
        entries = [p for p in data if render.connection_key(p) == name]
        for entry in entries:
            metrics = []
            for metric in sorted(usable_metrics(entry), key=render.metric_sort_key):
                percentage = render.metric_percentage(metric, selected)
                detail = render.metric_detail(metric)
                metrics.append({
                    "key": render.metric_key(metric),
                    "type": metric.get("type", "generic"),
                    "name": render.metric_title(metric, selected),
                    "percentage": percentage,
                    "value": render.metric_value(metric, selected),
                    "hasPercentage": percentage is not None,
                    "isAmount": render.metric_is_amount(metric),
                    "amount": metric.get("amount"),
                    "unit": metric.get("unit", ""),
                    "resetInSeconds": metric.get("reset_in_seconds"),
                    "detail": plain_text(detail),
                })
            if not metrics:
                continue
            providers.append({
                "id": name,
                "providerId": entry.get("_dir", name),
                "idx": entry.get("_idx", 0),
                "name": render.entry_name(entry),
                "logoPath": logo_paths.get(entry.get("_dir", name), ""),
                "loading": name in pending,
                "cached": bool(entry.get("_cached")),
                "error": plain_text(entry.get("_error") or ("No usage data available" if not metrics and name not in pending else "")),
                "metrics": metrics,
                "resetCredits": reset_credits.presentation(entry.get("reset_credits")),
                "resetAction": reset_actions.presentation(entry) if name not in pending else None,
                "monetaryCredits": usage_credits.presentation(entry),
            })
    current = next((p for p in providers if p["id"] == selected.get("provider") and p["idx"] == selected.get("idx", 0)), None)
    if current is None and providers:
        current = providers[0]
        selected.update(provider=current["id"], idx=current["idx"])
    if current and current["metrics"] and selected.get("metric") not in [m["key"] for m in current["metrics"]]:
        selected["metric"] = current["metrics"][0]["key"]
    enabled_data = [dict(p, metrics=usable_metrics(p)) for p in data if render.connection_key(p) in order and usable_metrics(p)]
    choices = render.get_bar_metric_choices(enabled_data, preferences) if "items" in preferences else state.get_selected_items(selected)
    bar_items = []
    for choice in choices:
        provider = next((p for p in providers if p["id"] == choice["provider"] and p["idx"] == choice["idx"]), None)
        if provider is None:
            continue
        loading = choice["provider"] in pending
        item_text = render._get_single_metric_text(enabled_data, dict(selected, **choice), spinner="…" if loading else None)
        item_logo = logo_paths.get(provider["providerId"], logo_path if choice == choices[0] else "") if state.get_icon_mode(selected) == "logo" else ""
        bar_items.append(dict(choice, text=item_text, logoPath=item_logo, loading=loading))
    if bar_items:
        selected.update({key: bar_items[0][key] for key in ("provider", "idx", "metric")})
        current = next(p for p in providers if p["id"] == selected["provider"] and p["idx"] == selected["idx"])
    elif "items" in preferences:
        selected = preferences
        current = None
    text = " · ".join(item["text"] for item in bar_items)
    if not current:
        text = "AI Status …" if pending else "AI Status"
        logo_path = ""
    elif state.get_icon_mode(selected) == "logo":
        logo_path = logo_paths.get(current["providerId"], logo_path)
    return {
        "schemaVersion": 1,
        "about": about.project_info(),
        "version": fetch.get_version_info(),
        "update": updates.update_guide(),
        "text": text,
        "barItems": bar_items,
        "selected": selected,
        "iconMode": state.get_icon_mode(selected),
        "logoPath": logo_path,
        "loading": bool(pending),
        "providers": providers,
        "settings": settings_snapshot(preferences if "items" in preferences else selected),
    }
