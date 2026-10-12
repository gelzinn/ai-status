"""Explicit redemption of one freshly verified Codex reset credit.

Contract: openai/codex, backend-client/src/client/rate_limit_resets.rs and
https://learn.chatgpt.com/docs/app-server#8-earned-rate-limit-resets-chatgpt
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from core.provider_http import QueryError, request
from core.reset_credits import count, expiry

RESET_CREDITS_URL = "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits"
CONSUME_URL = RESET_CREDITS_URL + "/consume"


def _authentication(env):
    # Providers ship as data files in frozen builds, so load the sibling collector.
    spec = importlib.util.spec_from_file_location("_ai_status_codex_query", Path(__file__).with_name("query.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.authentication(env)


def _uncertain(exc=None):
    error = QueryError("Could not confirm whether the reset was applied. Refresh usage before trying again.",
                       status=getattr(exc, "status", None),
                       retry_after_seconds=getattr(exc, "retry_after_seconds", None))
    error.reset_uncertain = True
    return error


def consume(env, credit_handle, request_id, verify_identity=None, before_send=None):
    """Use exactly the selected credit; never retry a mutation automatically."""
    if not isinstance(credit_handle, str) or not re.fullmatch(r"[a-f0-9]{64}", credit_handle):
        raise QueryError("Select a reset from the current account's reset details.")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise QueryError("Invalid reset request identifier.")
    headers = _authentication(env)
    account_id = headers.get("ChatGPT-Account-Id")
    if not isinstance(account_id, str) or not account_id.strip():
        raise QueryError("Reconnect this Codex account with its ChatGPT account ID before applying a reset.")
    headers = {**headers, "User-Agent": "codex-cli", "Content-Type": "application/json"}
    try:
        details = json.loads(request(RESET_CREDITS_URL, headers, timeout=7))
    except (ValueError, UnicodeError):
        raise QueryError("Could not verify the reset inventory. Refresh usage and try again.") from None
    credits = details.get("credits") if isinstance(details, dict) else None
    if not isinstance(credits, list) or count(details.get("available_count")) == 0:
        raise QueryError("No verified reset credits are available. Refresh usage.")
    now = datetime.now(timezone.utc)
    selected = None
    for item in credits:
        if not isinstance(item, dict) or item.get("status") != "available" or item.get("reset_type") != "codex_rate_limits":
            continue
        credit_id = item.get("id")
        if not isinstance(credit_id, str) or not credit_id or len(credit_id) > 512:
            continue
        if hashlib.sha256(credit_id.encode("utf-8")).hexdigest() != credit_handle:
            continue
        expires_at = item.get("expires_at")
        date = expiry(expires_at)
        if expires_at is not None and (date is None or date <= now):
            raise QueryError("This reset expired or its expiration could not be verified. Refresh usage.")
        selected = credit_id
        break
    if selected is None:
        raise QueryError("This reset is no longer available for this account. Refresh usage.")
    body = json.dumps({"redeem_request_id": request_id, "credit_id": selected}).encode("utf-8")
    if verify_identity is not None:
        verify_identity()
    if before_send is not None:
        before_send()
    try:
        result = json.loads(request(CONSUME_URL, headers, timeout=10, method="POST", data=body))
    except (QueryError, ValueError, UnicodeError) as exc:
        raise _uncertain(exc) from None
    code = result.get("code") if isinstance(result, dict) else None
    if not isinstance(code, str):
        raise _uncertain()
    if code in {"reset", "already_redeemed"}:
        return
    messages = {
        "nothing_to_reset": "There is no eligible usage window to reset. No reset was used.",
        "no_credit": "This reset is no longer available. No reset was used.",
    }
    if code in messages:
        error = QueryError(messages[code])
        error.reset_outcome = code
        raise error
    raise _uncertain()
