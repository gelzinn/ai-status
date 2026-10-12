#!/bin/bash
AUTH_FILE="$HOME/.codex/auth.json"
if [[ ! -f "$AUTH_FILE" ]]; then
  exit 0
fi

ACCESS=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['tokens']['access_token'])" 2>/dev/null)
ACCOUNT_ID=$(python3 -c "import json; print(json.load(open('$AUTH_FILE'))['tokens']['account_id'])" 2>/dev/null)

if [[ -z "$ACCESS" ]]; then
  exit 0
fi

USAGE=$(curl -s --max-time 10 \
  -H "Authorization: Bearer $ACCESS" \
  -H "ChatGPT-Account-Id: $ACCOUNT_ID" \
  "https://chatgpt.com/backend-api/wham/usage" 2>/dev/null || true)

# Details are optional: their failure must not discard usage or the banked count.
if jq -e '.rate_limit_reset_credits.available_count | type == "number" and . > 0' <<< "$USAGE" >/dev/null 2>&1; then
  DETAILS=$(curl -fsS --max-time 5 \
    -H "Authorization: Bearer $ACCESS" \
    -H "ChatGPT-Account-Id: $ACCOUNT_ID" \
    "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits" 2>/dev/null | python3 -c '
import hashlib, json, sys
try:
    details = json.load(sys.stdin)
    credits = details.get("credits") if isinstance(details, dict) else None
    if not isinstance(credits, list):
        sys.exit(1)
    rows = []
    for item in credits:
        if not isinstance(item, dict):
            continue
        row = {key: item.get(key) for key in ("status", "title", "expires_at")}
        credit_id = item.get("id")
        if sys.argv[1].strip() and item.get("reset_type") == "codex_rate_limits" and isinstance(credit_id, str) and credit_id:
            row["action_id"] = hashlib.sha256(credit_id.encode("utf-8")).hexdigest()
        rows.append(row)
    print(json.dumps({"credits": rows}))
except (ValueError, UnicodeError):
    sys.exit(1)
' "$ACCOUNT_ID" 2>/dev/null || true)
  # Keep only display fields and opaque handles; raw IDs never enter cache.
  ENRICHED=$(jq -c --argjson details "$DETAILS" '
    if ($details.credits | type) == "array" then
      .rate_limit_reset_credits.credits = $details.credits
    else . end' <<< "$USAGE" 2>/dev/null) || ENRICHED=""
  if [[ -n "$ENRICHED" ]]; then USAGE="$ENRICHED"; fi
fi
printf '%s\n' "$USAGE"
