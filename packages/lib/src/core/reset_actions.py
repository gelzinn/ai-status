"""Explicit, account-bound manual resets. Collection never calls this module."""
import hashlib
import importlib.util
import json
import math
import os
import re
import time
import uuid

from . import accounts, config, fetch, paths, render, reset_credits, state
from .provider_http import QueryError

SUPPORTED = {"claude", "codex"}
MAX_SNAPSHOT_AGE = 600


def _action_token(entry):
    fingerprint, observed = entry.get("_fingerprint"), entry.get("_observed_at")
    if (not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)
            or type(observed) not in (int, float) or not math.isfinite(observed)):
        return None
    value = [render.connection_key(entry), entry.get("_idx", 0), fingerprint, observed]
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode("utf-8")).hexdigest()


def _receipt_path(identity):
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return paths.CACHE_DIR / "reset-actions" / (digest + ".json")


def presentation(entry):
    """Offer actions only for fresh, identified inventory with usable handles."""
    if entry.get("_dir") not in SUPPORTED or entry.get("_cached") or entry.get("_error"):
        return None
    token = _action_token(entry)
    observed = entry.get("_observed_at", 0)
    if not token or not 0 <= time.time() - observed <= MAX_SNAPSHOT_AGE:
        return None
    receipt = paths.read_json(_receipt_path(render.connection_key(entry)))
    if not isinstance(receipt, dict) or receipt.get("token") == token:
        return None
    inventory = reset_credits.available_credits(entry.get("reset_credits"))
    if not any(item.get("action_id") for item in inventory["credits"]):
        return None
    return {"fingerprint": token}


def _provider(name):
    script = os.path.join(config.providers_dir(), name, "reset.py")
    spec = importlib.util.spec_from_file_location("reset_" + name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply(payload):
    """Revalidate the confirmed snapshot, then send one provider mutation."""
    if not isinstance(payload, dict) or payload.get("confirmed") is not True:
        raise ValueError("Confirm consumption of one reset credit before applying it.")
    identity, idx, token, handle = (payload.get(key) for key in ("provider", "idx", "fingerprint", "credit"))
    if (not isinstance(identity, str) or not identity or type(idx) is not int or idx != 0
            or not isinstance(token, str) or not re.fullmatch(r"[a-f0-9]{64}", token)
            or not isinstance(handle, str) or not re.fullmatch(r"[a-f0-9]{64}", handle)):
        raise ValueError("Invalid reset request; refresh the account and confirm again.")
    request_id = payload.get("requestId") or str(uuid.uuid4())
    try:
        uuid.UUID(request_id)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Invalid reset request identifier.") from None
    if not state.acquire_lock():
        raise ValueError("Another account operation is running. Wait for it to finish, then confirm again.")
    sent = False
    connection = None
    fingerprint = None
    try:
        connection = next((item for item in config.enabled_connections() if item["connection_id"] == identity), None)
        if connection is None or connection["provider"] not in SUPPORTED:
            raise ValueError("This account does not support applying resets here.")
        entry = next((item for item in state.load_cache()
                      if render.connection_key(item) == identity and item.get("_idx", 0) == idx), None)
        action = presentation(entry) if entry else None
        if not action or action["fingerprint"] != token:
            raise ValueError("These reset details changed or were already submitted. Refresh and confirm again.")
        inventory = reset_credits.available_credits(entry.get("reset_credits"))
        if not any(item.get("action_id") == handle for item in inventory["credits"]):
            raise ValueError("This reset credit is no longer available. Refresh the account.")
        env, fingerprint, _ = accounts.prepare(connection, capture_auth=True)
        if fingerprint != entry.get("_fingerprint"):
            raise ValueError("The account login changed. Refresh and confirm again.")

        def verify_identity():
            current = next((item for item in config.enabled_connections() if item["connection_id"] == identity), None)
            if current != connection or accounts.prepare(current)[1] != fingerprint:
                raise ValueError("The account login changed. Refresh and confirm again.")

        def before_send():
            nonlocal sent
            # Reserve before POST. Restarting or clicking in another frontend
            # cannot send this confirmed observation a second time.
            paths.atomic_json(_receipt_path(identity), {"token": token, "request_id": request_id,
                                                      "credit": handle, "submitted_at": time.time()})
            sent = True

        provider = _provider(connection["provider"])
        provider.consume(env, handle, request_id, verify_identity=verify_identity, before_send=before_send)
        return "Reset applied. Refreshing account usage…"
    except QueryError as error:
        if error.status == 429 and connection and fingerprint:
            fetch._save_cooldown(connection, fingerprint, error.retry_after_seconds or 300)
        raise ValueError(str(error)) from None
    except accounts.AccountError as error:
        raise ValueError(str(error)) from None
    except OSError:
        raise ValueError("Could not complete the reset. Refresh and check the account before confirming again.") from None
    except ValueError:
        raise
    except Exception:
        raise ValueError("Could not confirm the reset result. Refresh and check the account before applying another reset.") from None
    finally:
        # POST may have succeeded even if its response was lost. Invalidate only
        # this context, preserve the durable receipt, and request fresh usage.
        if sent and connection and fingerprint:
            try:
                directory = os.path.join(config.providers_dir(), connection["provider"])
                os.unlink(fetch._cache_path(directory, connection, fingerprint))
            except OSError:
                pass
        state.release_lock()
        if sent:
            try:
                state.trigger_refresh()
            except OSError:
                pass
