GitHub Copilot uses `GITHUB_COPILOT_TOKEN`, an existing OpenCode Copilot session, or a token from `gh auth token`. Sign in through OpenCode or run `gh auth login`, then enable **Copilot** in Settings.

## Requirements

- A GitHub account with Copilot access and a token from OpenCode, GitHub CLI, or `GITHUB_COPILOT_TOKEN`
- `jq` and `curl` (already required by AI Status)

## Step 1 — Authenticate Copilot in OpenCode

Run OpenCode's auth flow and pick **GitHub Copilot**:

```bash
opencode auth login
```

Complete the GitHub sign-in. OpenCode saves the token under the `github-copilot` key in:

```
~/.local/share/opencode/auth.json
```

AI Status reads `["github-copilot"].access` from that file.

## Step 2 — Enable it in AI Status

Right-click the AI Status module to open the config TUI, make sure **Copilot** is enabled, then left-click to refresh.

## What it tracks

Your Copilot chat and completions usage, with remaining counts.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows nothing / `{}` | No `github-copilot` token in OpenCode — run `opencode auth login` and pick GitHub Copilot. |
| Was working, now blank | Re-authenticate Copilot in OpenCode to refresh the token. |
| Confirm the token exists | `jq '."github-copilot"' ~/.local/share/opencode/auth.json` |

Run the provider's fetch script by hand to see the raw response:

```bash
bash ~/.local/share/ai-status/packages/lib/src/providers/copilot/query.sh
```

## Multiple accounts

Set `auth_file` to that account's OpenCode `auth.json`, or map `GITHUB_COPILOT_TOKEN` to its own environment variable. For GitHub CLI authentication, explicitly select the account's `GH_CONFIG_DIR`. There is no application-imposed account limit. See the [authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).
