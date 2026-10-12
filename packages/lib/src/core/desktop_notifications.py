"""Desktop delivery without importing a GUI toolkit into the collectors.

macOS's bundled app owns Notification Center permission and delivery. Its
durable outbox bridges the Python collector and Swift host; queued events are
short lived so reconnecting an app never presents old quota observations.
"""
from contextlib import contextmanager
import atexit
import copy
import os
import subprocess
import sys
import threading
import time

from . import paths

MAX_AGE_SECONDS = 300
MAX_PENDING = 100
LINUX_HANDSHAKE_SECONDS = 3
LINUX_ACTION_WAIT_SECONDS = 300
_linux_processes = set()
_linux_process_lock = threading.Lock()


def _stop_notifier(process):
    """Reap a stalled action listener without waiting on desktop user input."""
    try:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=1)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _stop_linux_notifiers():
    with _linux_process_lock:
        processes = list(_linux_processes)
    for process in processes:
        _stop_notifier(process)


atexit.register(_stop_linux_notifiers)


def _activate_linux(event):
    """Only an existing, enabled metric can become a notification destination."""
    from . import quickshell

    selection = {key: event.get(key) for key in ("provider", "idx", "metric")}
    try:
        quickshell.select_metric(selection)
        paths.atomic_json(paths.RUNTIME_DIR / "notification-activation.json",
                          dict(selection, id=event["id"], time=time.time()))
    except (OSError, ValueError):
        pass


def _deliver_linux(event):
    urgency = "critical" if event.get("kind") == "exhausted" or event.get("threshold", 0) == 100 else "normal"
    arguments = ["notify-send", "--app-name=AI Status", "--category=quota",
                 "--icon=" + str(paths.LIB_DIR / "assets/app.png"), "--urgency=" + urgency]
    process = subprocess.Popen(
        arguments + ["--print-id", "--action=default=Open", "--wait", "--expire-time=10000",
                     "--", event["title"], event["body"]],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        bufsize=0,
    )
    with _linux_process_lock:
        _linux_processes.add(process)
    ready = threading.Event()
    outcome = {"accepted": False, "retry": False}
    context = copy.deepcopy(event)

    def watch():
        try:
            # libnotify flushes --print-id immediately after the server accepts
            # the notification. Unbuffered bytes keep later action output intact.
            identity = process.stdout.readline().strip()
            if identity.isdigit() and int(identity) > 0:
                outcome["accepted"] = True
                ready.set()
                action, _ = process.communicate(timeout=LINUX_ACTION_WAIT_SECONDS)
                if b"default" in action.splitlines():
                    _activate_linux(context)
            else:
                outcome["retry"] = process.wait(timeout=1) != 0
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        finally:
            ready.set()
            _stop_notifier(process)
            if process.stdout:
                process.stdout.close()
            with _linux_process_lock:
                _linux_processes.discard(process)

    threading.Thread(target=watch, daemon=True, name="ai-status-notification-action").start()
    if not ready.wait(LINUX_HANDSHAKE_SECONDS):
        _stop_notifier(process)
        return False
    if outcome["accepted"]:
        return True
    if outcome["retry"]:
        # Older notify-send versions reject action options before submitting;
        # retry only that failure, never an accepted notification or a timeout.
        result = subprocess.run(
            arguments + ["--", event["title"], event["body"]],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=3, check=False,
        )
        return result.returncode == 0
    return False


def queue_file():
    return paths.CONFIG_DIR / "native-alerts.json"


@contextmanager
def _locked():
    filename = queue_file()
    filename.parent.mkdir(parents=True, exist_ok=True)
    with open(filename.with_suffix(".lock"), "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield filename
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock, fcntl.LOCK_UN)


def _read(filename, now):
    document = paths.read_json(filename)
    entries = document.get("events", []) if isinstance(document, dict) else []
    if not isinstance(entries, list):
        return []
    result = []
    for event in entries:
        if not isinstance(event, dict) or any(not isinstance(event.get(key), str)
                                              for key in ("id", "title", "body", "kind", "provider", "metric")):
            continue
        if type(event.get("idx")) is not int or event["idx"] < 0:
            continue
        if event.get("kind") == "threshold" and (type(event.get("threshold")) is not int or not 1 <= event["threshold"] <= 100):
            continue
        if "observed_at" in event and (isinstance(event["observed_at"], bool)
                or not isinstance(event["observed_at"], (int, float)) or not event["observed_at"] >= 0):
            continue
        if any(key in event and (not isinstance(event[key], list) or not all(isinstance(value, str) for value in event[key]))
               for key in ("observed_metrics", "recovered_metrics", "blocked_metrics")):
            continue
        queued = event.get("queued_at")
        if isinstance(queued, bool) or not isinstance(queued, (int, float)):
            continue
        if 0 <= now - queued <= MAX_AGE_SECONDS:
            result.append(event)
    return result


def _enqueue(event):
    now = time.time()
    with _locked() as filename:
        entries = _read(filename, now)
        if any(item["id"] == event["id"] for item in entries):
            return True
        if len(entries) >= MAX_PENDING:
            return False
        entries.append(dict(copy.deepcopy(event), queued_at=now))
        paths.atomic_json(filename, {"events": entries})
    return True


def _current_observations(providers, now):
    from . import notifications, render

    current = {}
    for entry in providers if isinstance(providers, list) else []:
        observation = notifications._observation(entry, now)
        if observation is None:
            continue
        connection, idx, observed, fingerprint = observation
        values, malformed = {}, False
        for metric in entry["metrics"]:
            percentage = notifications._quota(metric)
            if percentage is None:
                if isinstance(metric, dict) and metric.get("type") in notifications._QUOTA_TYPES and "amount" not in metric:
                    malformed = True
                continue
            try:
                key = render.metric_key(metric)
            except (AttributeError, TypeError):
                malformed = True
                continue
            if key in values:
                malformed = True
            values[key] = percentage
        identity = connection, idx
        if identity not in current or observed > current[identity]["observed_at"]:
            current[identity] = {"observed_at": observed, "fingerprint": fingerprint,
                                 "identity": entry.get("_notification_identity") or fingerprint,
                                 "metrics": values, "malformed": malformed}
    return current


def _still_relevant(event, current):
    sample = current.get((event.get("provider"), event.get("idx", 0)))
    # A failed/cache-only poll cannot contradict a queued fresh observation.
    if sample is None:
        return True
    if sample["observed_at"] < event.get("observed_at", 0):
        return True
    identity = event.get("identity")
    if identity and identity != sample["identity"]:
        return False
    if not identity and event.get("fingerprint") and event["fingerprint"] != sample["fingerprint"]:
        return False
    metrics = sample["metrics"]
    if event.get("kind") == "threshold":
        return event.get("metric") in metrics and metrics[event["metric"]] >= event.get("threshold", 100)
    if event.get("kind") == "recovery":
        known = event.get("observed_metrics", [event.get("metric")])
        return (bool(metrics) and not sample["malformed"] and set(known).issubset(metrics)
                and all(percentage < 100 for percentage in metrics.values()))
    if event.get("kind") == "partial_recovery":
        recovered, blocked = event.get("recovered_metrics", []), event.get("blocked_metrics", [])
        return (bool(recovered) and not sample["malformed"] and set(recovered).issubset(metrics)
                and all(metrics[key] < 100 for key in recovered)
                and {key for key, percentage in metrics.items() if percentage >= 100} == set(blocked))
    return True


def pending(providers=None):
    """Return fresh events; an absent or contended outbox is a harmless skip."""
    try:
        with _locked() as filename:
            from . import notifications

            settings = notifications.load_settings()
            now = time.time()
            entries = _read(filename, now)
            if notifications.is_silent(settings):
                if entries:
                    paths.atomic_json(filename, {"events": []})
                return []
            rules = {(rule["connection_id"], rule["metric"]): rule for rule in settings["rules"]}
            current = _current_observations(providers, now)
            filtered = []
            for event in entries:
                rule = rules.get((event.get("provider"), event.get("metric")),
                                 rules.get((event.get("provider"), "*"), settings))
                if not rule["enabled"]:
                    continue
                if event.get("kind") in ("recovery", "partial_recovery") and not settings["recovery"]:
                    continue
                if event.get("kind") == "threshold" and event.get("threshold") not in rule["thresholds"]:
                    continue
                if not _still_relevant(event, current):
                    continue
                filtered.append(event)
            if filtered != entries:
                paths.atomic_json(filename, {"events": filtered})
            return filtered
    except (OSError, ValueError, TypeError, ImportError):
        return []


def ack(ids):
    """Remove only IDs the native app successfully submitted to Notification Center."""
    if not isinstance(ids, (list, tuple)) or not all(isinstance(identity, str) for identity in ids):
        raise ValueError("Notification IDs must be strings.")
    with _locked() as filename:
        entries = [event for event in _read(filename, time.time()) if event["id"] not in ids]
        paths.atomic_json(filename, {"events": entries})


def deliver(event, frontend="waybar"):
    """Report whether the OS accepted delivery or the native app's durable outbox."""
    if not isinstance(event, dict) or any(not isinstance(event.get(key), str) for key in ("id", "title", "body")):
        return False
    try:
        if sys.platform == "darwin":
            return _enqueue(event)
        if sys.platform.startswith("linux"):
            return _deliver_linux(event)
    except (OSError, ValueError, ImportError, subprocess.TimeoutExpired):
        pass
    # Windows owns delivery in the tray event callback, where Qt is available.
    return False
