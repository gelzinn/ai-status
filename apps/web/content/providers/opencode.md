OpenCode's usage dashboard has no public API, so ai-status reads your quota the same way your browser does — by replaying an authenticated request to `opencode.ai`. You provide two things from a logged-in session: your **workspace ID** and a **session cookie**. It's more hands-on than the OAuth providers, but it's a one-time setup.

> Because this relies on a session cookie, it can stop working when you log out or the cookie expires. If OpenCode goes stale, redo **Step 2** to refresh the cookie.

## Requirements

- An OpenCode account you can log into at [opencode.ai](https://opencode.ai)
- A browser with DevTools (any Chromium- or Firefox-based one)
- `python3`, `curl` and `jq` (already required by ai-status)

## Step 1 — Find your workspace ID

Log in at [opencode.ai](https://opencode.ai) and open your workspace. The URL looks like:

```
https://opencode.ai/workspace/ws_a1b2c3d4/go
```

The segment after `/workspace/` — `ws_a1b2c3d4` above — is your **workspace ID**. Copy it.

## Step 2 — Copy your session cookie

1. On that same page, open DevTools — press `F12` (or right-click → **Inspect**).
2. Open the **Network** tab and reload the page.
3. Click any request made to `opencode.ai`.
4. Under **Request Headers**, find the **`Cookie`** header and copy its full value.

> The cookie authenticates you — treat it like a password. Don't paste it into anything public, and never commit it to git.

## Step 3 — Create the config file

ai-status reads both values from `~/.config/opencode-bar/opencode-go.json`:

```bash
mkdir -p ~/.config/opencode-bar
cat > ~/.config/opencode-bar/opencode-go.json <<'EOF'
{
  "workspaceId": "ws_a1b2c3d4",
  "authCookie": "<paste the full Cookie header here>"
}
EOF
chmod 600 ~/.config/opencode-bar/opencode-go.json
```

`chmod 600` keeps the file readable only by your user.

## Step 4 — Enable it in ai-status

Right-click the ai-status module to open the config TUI, make sure **OpenCode** is enabled, then left-click to refresh. Within a few seconds you'll see OpenCode's usage in the tooltip.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows `0%` or "API unreachable" | The cookie likely expired — redo **Step 2** and update `authCookie`. |
| Nothing appears at all | Confirm OpenCode is enabled in the config TUI and the JSON file is valid (`jq . ~/.config/opencode-bar/opencode-go.json`). |
| Wrong numbers | Double-check the **workspace ID** matches the workspace whose quota you want. |

You can also run the provider's fetch script by hand to see the raw response:

```bash
bash ~/.local/share/ai-status/packages/lib/src/providers/opencode/query.sh
```
