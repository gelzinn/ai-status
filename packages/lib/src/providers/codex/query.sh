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
    "https://chatgpt.com/backend-api/wham/rate-limit-reset-credits" 2>/dev/null || true)
  # Project display fields only; redemption IDs never enter the provider cache.
  ENRICHED=$(jq -c --argjson details "$DETAILS" '
    if ($details.credits | type) == "array" then
      .rate_limit_reset_credits.credits = [
        $details.credits[] | select(type == "object") | {status, title, expires_at}
      ]
    else . end' <<< "$USAGE" 2>/dev/null) || ENRICHED=""
  if [[ -n "$ENRICHED" ]]; then USAGE="$ENRICHED"; fi
fi
printf '%s\n' "$USAGE"
