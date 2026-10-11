OpenCode Go exposes a read-only usage endpoint. AI Status reads `opencode-go.key` from `~/.local/share/opencode/auth.json`, or uses `OPENCODE_GO_API_KEY`. No workspace ID or browser session cookie is required.

## Setup

Connect OpenCode Go through `opencode auth login`, or supply `OPENCODE_GO_API_KEY` to the AI Status process. Enable **OpenCode** in Settings and refresh.

## What it tracks

Rolling, weekly, and monthly quota percentages with reset timers, when reported by your account.

## Multiple accounts

Add a connection with its own `auth_file` pointing to an OpenCode `auth.json`, or map `OPENCODE_GO_API_KEY` to a separate environment variable. There is no application-imposed account limit. See the [authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

## Troubleshooting

If authentication fails, reconnect OpenCode Go or check that the selected credential file contains `opencode-go.key`. The legacy `opencode-go.json` cookie configuration is no longer used.
