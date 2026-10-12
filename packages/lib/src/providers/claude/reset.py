"""Explicit redemption of an eligible Claude cedar_ember reset grant.

Contract inspected statically in Anthropic's Claude Code 2.1.296 distribution:
POST /api/organizations/{organization.uuid}/reset_rate_limits with program,
grant_id and request_id. Resolve organization via OAuth profile for this bearer.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import uuid

from core.provider_http import QueryError, request
from core.reset_credits import count, expiry

API_BASE = "https://api.anthropic.com"
PROFILE_URL = API_BASE + "/api/oauth/profile"
USAGE_URL = API_BASE + "/api/oauth/usage?cedar_ember=1&skip_spend=1"


def _authentication(env):
    # Providers ship as data files in frozen builds, so load the sibling collector.
    spec = importlib.util.spec_from_file_location("_ai_status_claude_query", Path(__file__).with_name("query.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    headers, _ = module.authentication(env)
    return {**headers, "Content-Type": "application/json"}


def _uncertain(exc=None):
    error = QueryError("Could not confirm whether the reset was applied. Refresh usage before trying again.",
                       status=getattr(exc, "status", None),
                       retry_after_seconds=getattr(exc, "retry_after_seconds", None))
    error.reset_uncertain = True
    return error


def consume(env, credit_handle, request_id, verify_identity=None, before_send=None):
    """Use the service's next eligible grant with one captured OAuth credential."""
    if not isinstance(credit_handle, str) or not re.fullmatch(r"[a-f0-9]{64}", credit_handle):
        raise QueryError("Select a reset from the current account's reset details.")
    if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", request_id):
        raise QueryError("Invalid reset request identifier.")
    headers = _authentication(env)
    try:
        profile = json.loads(request(PROFILE_URL, headers, timeout=6))
        usage = json.loads(request(USAGE_URL, headers, timeout=7))
    except (ValueError, UnicodeError):
        raise QueryError("Could not verify this Claude account and its resets. Refresh usage and try again.") from None
    organization = profile.get("organization") if isinstance(profile, dict) else None
    organization_id = organization.get("uuid") if isinstance(organization, dict) else None
    try:
        if not isinstance(organization_id, str) or str(uuid.UUID(organization_id)) != organization_id.lower():
            raise ValueError
    except ValueError:
        raise QueryError("This login did not identify a Claude organization. Sign in again before applying a reset.") from None
    block = usage.get("cedar_ember") if isinstance(usage, dict) else None
    grants = block.get("grants") if isinstance(block, dict) else None
    if not isinstance(grants, list) or block.get("eligible") is not True:
        raise QueryError("No eligible Claude reset is available for this account. Refresh usage.")
    now = datetime.now(timezone.utc)
    cooldown = block.get("cooldown_until")
    cooldown_at = expiry(cooldown)
    if cooldown is not None and (cooldown_at is None or cooldown_at > now):
        raise QueryError("This Claude reset is cooling down. Refresh usage later.")
    selected = None
    for grant in grants:
        if not isinstance(grant, dict):
            continue
        grant_id = grant.get("id")
        if not isinstance(grant_id, str) or not re.fullmatch(r"[a-z0-9_-]{1,40}", grant_id):
            continue
        if hashlib.sha256(grant_id.encode("utf-8")).hexdigest() != credit_handle:
            continue
        if block.get("next_grant_id") != grant_id or grant.get("usable_now") is not True or grant.get("paused") or count(grant.get("resets_left")) == 0:
            raise QueryError("This Claude reset is no longer offered for use. Refresh usage.")
        ends_at = grant.get("ends_at")
        date = expiry(ends_at)
        if ends_at is not None and (date is None or date <= now):
            raise QueryError("This reset expired or its expiration could not be verified. Refresh usage.")
        starts_at = grant.get("starts_at")
        starts = expiry(starts_at)
        if starts_at is not None and (starts is None or starts > now):
            raise QueryError("This Claude reset is not available yet. Refresh usage later.")
        if grant.get("use_requires_limit", True) is not False and block.get("at_limit") is not True:
            raise QueryError("This Claude reset can only be applied after reaching a usage limit. No reset was used.")
        blocking = grant.get("blocking")
        if isinstance(blocking, list) and blocking:
            raise QueryError("This reset does not clear an active Claude limit. Refresh usage after that limit resets.")
        selected = grant_id
        break
    if selected is None:
        raise QueryError("This reset is no longer available for this account. Refresh usage.")
    url = f"{API_BASE}/api/organizations/{organization_id}/reset_rate_limits"
    body = json.dumps({"program": "cedar_ember", "grant_id": selected, "request_id": request_id}).encode("utf-8")
    if verify_identity is not None:
        verify_identity()
    if before_send is not None:
        before_send()
    try:
        result = json.loads(request(url, headers, timeout=10, method="POST", data=body))
    except (QueryError, ValueError, UnicodeError) as exc:
        raise _uncertain(exc) from None
    outcome = result.get("result") if isinstance(result, dict) else None
    if not isinstance(outcome, str):
        raise _uncertain()
    if outcome == "reset":
        return
    messages = {
        "already_used": "This Claude reset was already used. Refresh usage to see the current limits.",
        "not_limited": "There is no eligible Claude usage limit to reset. No reset was used.",
        "cooldown": "This Claude reset is cooling down. No reset was used.",
        "ineligible": "This Claude reset is not eligible for use right now. No reset was used.",
    }
    if outcome in messages:
        error = QueryError(messages[outcome])
        error.reset_outcome = outcome
        raise error
    raise _uncertain()
