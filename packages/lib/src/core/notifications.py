"""Persistent quota alerts shared by every desktop collector.

Only fresh successful observations can produce events. Delivery runs while a
portable file lock is held, so frontends sharing a profile cannot notify twice.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import math
import os
import re
import threading
import time

from . import paths, render

MAX_OBSERVATION_AGE = 600
RECENT_ACTIVITY_SECONDS = 86400
DEFAULT_SETTINGS = {
    "enabled": True,
    "thresholds": [80, 95, 100],
    "recovery": True,
    "recent_only": False,
    "muted_until": 0,
    "quiet_hours": {"start": "", "end": ""},
    "work_hours": {"start": "", "end": ""},
    "rules": [],
}
_THREAD_LOCK = threading.Lock()
_QUOTA_TYPES = {"rolling", "daily", "weekly", "monthly", "generic"}


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    except (ValueError, OverflowError):
        return None


def _thresholds(value):
    if not isinstance(value, list) or any(type(v) is not int or not 1 <= v <= 100 for v in value):
        raise ValueError("Notification thresholds must be whole percentages from 1 to 100.")
    if len(set(value)) != len(value):
        raise ValueError("Notification thresholds must not contain duplicates.")
    return sorted(value)


def _hours(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must contain start and end times.")
    start, end = value.get("start", ""), value.get("end", "")
    if not isinstance(start, str) or not isinstance(end, str):
        raise ValueError(f"{name} times must use HH:MM.")
    if bool(start) != bool(end) or any(v and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", v) for v in (start, end)):
        raise ValueError(f"{name} times must use HH:MM, with both start and end set.")
    if start and start == end:
        raise ValueError(f"{name} start and end must differ.")
    return {"start": start, "end": end}


def validate_settings(settings):
    """Normalize a settings document, rejecting values that could hide errors."""
    if not isinstance(settings, dict):
        raise ValueError("Notification settings must be an object.")
    result = deepcopy(DEFAULT_SETTINGS)
    for key in ("enabled", "recovery", "recent_only"):
        value = settings.get(key, result[key])
        if type(value) is not bool:
            raise ValueError(f"Notification {key} must be true or false.")
        result[key] = value
    result["thresholds"] = _thresholds(settings.get("thresholds", result["thresholds"]))
    muted = _number(settings.get("muted_until", 0))
    if muted is None or muted < 0:
        raise ValueError("Notification mute deadline must be a nonnegative timestamp.")
    result["muted_until"] = muted
    for key in ("quiet_hours", "work_hours"):
        result[key] = _hours(settings.get(key, result[key]), key)
    rules = settings.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("Notification rules must be a list.")
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("Each notification rule must be an object.")
        connection, metric = rule.get("connection_id"), rule.get("metric")
        if not isinstance(connection, str) or not connection or not isinstance(metric, str) or not metric:
            raise ValueError("Notification rules require a connection_id and metric key.")
        if (connection, metric) in seen:
            raise ValueError("Only one notification rule is allowed per connection and window.")
        seen.add((connection, metric))
        enabled = rule.get("enabled", True)
        if type(enabled) is not bool:
            raise ValueError("Notification rule enabled must be true or false.")
        result["rules"].append({"connection_id": connection, "metric": metric,
                                "enabled": enabled,
                                "thresholds": _thresholds(rule.get("thresholds", result["thresholds"]))})
    return result


def load_settings():
    """Read persisted preferences without making invalid files crash collection."""
    try:
        return validate_settings(paths.read_json(paths.CONFIG_DIR / "notifications.json"))
    except (ValueError, TypeError):
        return deepcopy(DEFAULT_SETTINGS)


def save_settings(settings):
    result = validate_settings(settings)
    paths.atomic_json(paths.CONFIG_DIR / "notifications.json", result)
    return result


@contextmanager
def _locked_state():
    paths.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK, open(paths.CONFIG_DIR / "notification-state.lock", "a+b") as stream:
        if os.name == "nt":
            import msvcrt
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _in_hours(now, hours):
    if not hours["start"]:
        return False
    current = datetime.fromtimestamp(now).strftime("%H:%M")
    start, end = hours["start"], hours["end"]
    return start <= current < end if start < end else current >= start or current < end


def _silent(settings, now):
    return (not settings["enabled"] or now < settings["muted_until"]
            or _in_hours(now, settings["quiet_hours"])
            or bool(settings["work_hours"]["start"]) and not _in_hours(now, settings["work_hours"]))


def is_silent(settings=None, now=None):
    """Whether queued desktop events should currently be suppressed."""
    return _silent(load_settings() if settings is None else validate_settings(settings),
                   time.time() if now is None else now)


def _quota(metric):
    if not isinstance(metric, dict) or not isinstance(metric.get("type"), str) or metric["type"] not in _QUOTA_TYPES:
        return None
    if any(metric.get(key) is not None and not isinstance(metric[key], str) for key in ("name", "title", "id", "detail")):
        return None
    # Monetary balances and API budgets also expose percentages; they are not
    # the subscription windows that can block Claude or Codex usage.
    if "amount" in metric or metric.get("unit") in ("USD", "credits") or metric.get("value_format") == "amount_ratio":
        return None
    percentage = _number(metric.get("percentage"))
    return percentage if percentage is not None and 0 <= percentage <= 100 else None


def _observation(entry, now):
    if not isinstance(entry, dict) or entry.get("_cached") or entry.get("_error") or entry.get("error"):
        return None
    observed, fingerprint = _number(entry.get("_observed_at")), entry.get("_fingerprint")
    connection = render.connection_key(entry)
    if (observed is None or observed > now + 5 or now - observed > MAX_OBSERVATION_AGE
            or not isinstance(fingerprint, str) or not fingerprint
            or not isinstance(connection, str) or not connection
            or not isinstance(entry.get("metrics"), list)):
        return None
    idx = entry.get("_idx", 0)
    if type(idx) is not int or idx < 0:
        return None
    identity = entry.get("_notification_identity") or fingerprint
    if not isinstance(identity, str):
        return None
    return connection, idx, observed, identity


def _reset(metric, observed):
    absolute = _number(metric.get("reset_at"))
    if absolute is not None and absolute > 0:
        return absolute
    relative = _number(metric.get("reset_in_seconds"))
    return observed + relative if relative is not None and relative > 0 else None


def _rule(settings, connection, metric):
    for rule in settings["rules"]:
        if rule["connection_id"] == connection and rule["metric"] == metric:
            return rule
    for rule in settings["rules"]:
        if rule["connection_id"] == connection and rule["metric"] == "*":
            return rule
    return {"enabled": True, "thresholds": settings["thresholds"]}


def _reset_text(reset, now):
    if reset is None:
        return "Reset time unavailable."
    seconds = max(0, reset - now)
    if seconds >= 86400:
        return f"Resets in {math.ceil(seconds / 86400)} days."
    if seconds >= 3600:
        return f"Resets in {math.ceil(seconds / 3600)} hours."
    return f"Resets in {max(1, math.ceil(seconds / 60))} minutes."


def _metric_title(metric):
    title = render.metric_title(metric)
    detail = metric.get("detail") or ""
    if not metric.get("name") and not metric.get("id") and " · " in detail:
        scope = detail.split(" · ", 1)[0].strip()
        if scope:
            title += " · " + scope
    return title


def _event(entry, key, kind, episode, body, **values):
    connection = render.connection_key(entry)
    identity = json.dumps([connection, entry.get("_idx", 0), key, kind, episode], separators=(",", ":"))
    title = {"recovery": "Quota recovered", "partial_recovery": "Quota still blocked"}.get(kind, "Quota alert")
    return {"id": hashlib.sha256(identity.encode()).hexdigest()[:24],
            "title": "AI Status · " + title,
            "body": body, "kind": kind, "provider": connection,
            "idx": entry.get("_idx", 0), "metric": key,
            "observed_at": entry["_observed_at"], "fingerprint": entry["_fingerprint"],
            "identity": entry.get("_notification_identity") or entry["_fingerprint"], **values}


def _send(deliver, event):
    try:
        return bool(deliver(event))
    except Exception:
        return False


def _valid_group(group):
    if not isinstance(group, dict) or not isinstance(group.get("metrics"), dict):
        return False
    if type(group.get("blocked")) is not bool or type(group.get("episode")) is not int or group["episode"] < 0:
        return False
    if any(_number(group.get(key)) is None or group[key] < 0 for key in ("observed_at", "last_activity_at")):
        return False
    for key, metric in group["metrics"].items():
        if not isinstance(key, str) or not isinstance(metric, dict):
            return False
        percentage = _number(metric.get("percentage"))
        if percentage is None or not 0 <= percentage <= 100:
            return False
        if metric.get("reset_at") is not None and (_number(metric["reset_at"]) is None or metric["reset_at"] <= 0):
            return False
        if (type(metric.get("cycle")) is not int or metric["cycle"] < 0
                or not isinstance(metric.get("notified"), list)
                or any(type(value) is not int or not 1 <= value <= 100 for value in metric["notified"])
                or not isinstance(metric.get("title"), str)):
            return False
    blocked = group.get("episode_blocked", [])
    partials = group.get("partial_notified", [])
    return (isinstance(blocked, list) and all(isinstance(key, str) and key in group["metrics"] for key in blocked)
            and isinstance(partials, list) and all(isinstance(value, str) for value in partials))


def _process(providers, deliver, settings, document, now):
    records = document.setdefault("connections", {})
    delivered = []
    silent = _silent(settings, now)
    for entry in providers:
        observation = _observation(entry, now)
        if observation is None:
            continue
        connection, idx, observed, fingerprint = observation
        group_key = json.dumps([connection, idx], separators=(",", ":"))
        group = records.get(group_key)
        if not _valid_group(group) or group.get("fingerprint") != fingerprint:
            group = {"fingerprint": fingerprint, "metrics": {}, "blocked": False,
                     "episode": 0, "last_activity_at": 0, "observed_at": 0}
            records[group_key] = group
        group.setdefault("episode_blocked", [])
        group.setdefault("partial_notified", [])
        if observed <= group.get("observed_at", 0):
            continue
        group["observed_at"] = observed
        previous_blocked = group["blocked"]
        metrics = group["metrics"]
        current = {}
        malformed = False
        for metric in entry["metrics"]:
            percentage = _quota(metric)
            if percentage is None:
                if (isinstance(metric, dict) and isinstance(metric.get("type"), str)
                        and metric["type"] in _QUOTA_TYPES and "amount" not in metric):
                    malformed = True
                continue
            try:
                key = render.metric_key(metric)
            except (AttributeError, TypeError):
                malformed = True
                continue
            if key in current:
                malformed = True
                continue
            current[key] = (metric, percentage)
        known = set(metrics)
        for key, (metric, percentage) in current.items():
            reset = _reset(metric, observed)
            prior = metrics.get(key)
            if prior is None:
                prior = {"percentage": percentage, "reset_at": reset, "notified": [], "cycle": 0}
                metrics[key] = prior
                if percentage > 0:
                    group["last_activity_at"] = observed
            else:
                old_percentage, old_reset = prior["percentage"], prior.get("reset_at")
                if percentage > old_percentage:
                    group["last_activity_at"] = observed
                dropped = percentage < old_percentage
                # Deadline estimates vary on each query. Rearm only after a
                # confirmed consumption drop, never because a timer changed.
                reset_changed = reset is not None and old_reset is not None and reset - old_reset > 60
                reset_elapsed = old_reset is not None and observed >= old_reset
                manual_reset = percentage == 0 and old_percentage > 0
                if dropped and (reset_changed or reset_elapsed or manual_reset):
                    prior["notified"] = []
                    prior["cycle"] += 1
                prior["percentage"] = percentage
                # Keep the old deadline when changes are only rounding jitter.
                if old_reset is None or reset is None or abs(reset - old_reset) > 60:
                    prior["reset_at"] = reset
            prior["title"] = _metric_title(metric)
            rule = _rule(settings, connection, key)
            reached = [v for v in rule["thresholds"] if percentage >= v]
            unseen = [v for v in reached if v not in prior["notified"]]
            if unseen:
                threshold = max(unseen)
                # A jump across several limits produces one useful alert.
                prior["notified"] = sorted(set(prior["notified"] + [v for v in reached if v < threshold]))
                body = (f"{render.entry_name(entry)}: {percentage:g}% of {_metric_title(metric)} quota used. "
                        + _reset_text(reset, now))
                event = _event(entry, key, "threshold", [fingerprint, prior["cycle"], threshold], body,
                               percentage=percentage, threshold=threshold, reset_at=reset)
                if silent or not rule["enabled"]:
                    prior["notified"] = sorted(set(prior["notified"] + reached))
                else:
                    unreserved = prior["notified"]
                    prior["notified"] = sorted(set(prior["notified"] + reached))
                    if _send(deliver, event):
                        delivered.append(event)
                    else:
                        prior["notified"] = unreserved
        blocked_keys = {key for key, metric in metrics.items() if metric["percentage"] >= 100}
        complete = bool(current) and not malformed and known.issubset(current)
        recent = now - group["last_activity_at"] <= RECENT_ACTIVITY_SECONDS
        recovery_silent = silent or not settings["recovery"] or settings["recent_only"] and not recent
        if blocked_keys:
            if not previous_blocked:
                group["episode"] += 1
                group["episode_blocked"] = []
                group["partial_notified"] = []
            group["blocked"] = True
            episode_blocked = set(group.get("episode_blocked", [])) | blocked_keys
            group["episode_blocked"] = sorted(episode_blocked)
            recovered = episode_blocked - blocked_keys
            signature = json.dumps([sorted(recovered), sorted(blocked_keys)], separators=(",", ":"))
            if complete and recovered and signature not in group["partial_notified"]:
                first_key = sorted(recovered)[0]
                recovered_names = ", ".join(metrics[key]["title"] for key in sorted(recovered))
                blocked_names = ", ".join(metrics[key]["title"] for key in sorted(blocked_keys))
                event = _event(entry, first_key, "partial_recovery", [fingerprint, group["episode"], signature],
                               f"{render.entry_name(entry)}: {recovered_names} quota recovered. "
                               f"Still blocked by exhausted {blocked_names} quota.",
                               recovered_metrics=sorted(recovered), blocked_metrics=sorted(blocked_keys))
                if recovery_silent:
                    group["partial_notified"].append(signature)
                else:
                    group["partial_notified"].append(signature)
                    if _send(deliver, event):
                        delivered.append(event)
                    else:
                        group["partial_notified"].remove(signature)
        elif previous_blocked and complete:
            # A rolling reset is not recovery while a weekly/model window is
            # still exhausted, or omitted from the fresh provider response.
            first_key = next(iter(current))
            event = _event(entry, first_key, "recovery", [fingerprint, group["episode"]],
                           f"{render.entry_name(entry)}: quota available again. All observed quota windows are below 100%.",
                           observed_metrics=sorted(current))
            if recovery_silent:
                group["blocked"] = False
            else:
                group["blocked"] = False
                if _send(deliver, event):
                    delivered.append(event)
                else:
                    group["blocked"] = True
    return delivered


def process(providers, deliver, now=None):
    """Deliver threshold/recovery events and persist suppression across restarts.

    ``deliver(event)`` returns true once the platform accepted the event. Failed
    deliveries are retried on the next fresh sample. Persist the reservation
    before invoking the platform, preferring a missed event after a crash over
    repeated delivery. A read-only profile never produces unrecorded alerts.
    """
    now = time.time() if now is None else now
    if not isinstance(providers, list) or _number(now) is None:
        return []
    try:
        with _locked_state():
            settings = load_settings()
            document = paths.read_json(paths.CONFIG_DIR / "notification-state.json")
            if not isinstance(document, dict) or document.get("version") != 1 or not isinstance(document.get("connections"), dict):
                document = {"version": 1, "connections": {}}
            def reserved_delivery(event):
                # _process has already marked this event consumed. Commit that
                # reservation before any external side effect, under the lock.
                paths.atomic_json(paths.CONFIG_DIR / "notification-state.json", document)
                return deliver(event)

            events = _process(providers, reserved_delivery, settings, document, now)
            paths.atomic_json(paths.CONFIG_DIR / "notification-state.json", document)
            return events
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return []


def next_check_delay(providers, default=300, now=None):
    """Schedule a fresh check soon after an exhausted window's known reset."""
    now = time.time() if now is None else now
    delay = max(1, default)
    if not isinstance(providers, list):
        return delay
    for entry in providers:
        observation = _observation(entry, now)
        if observation is None:
            continue
        observed = observation[2]
        for metric in entry["metrics"]:
            percentage = _quota(metric)
            reset = _reset(metric, observed) if percentage is not None else None
            if percentage is not None and percentage >= 100 and reset is not None and reset > observed:
                # Avoid spinning when the provider postpones its reset. A clock
                # deadline requests fresh data; it does not imply recovery.
                delay = min(delay, max(15, reset - now + 5))
    return delay
