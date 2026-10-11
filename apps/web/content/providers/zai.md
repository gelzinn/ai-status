Z.AI is tracked through **OpenCode**: when you add your Z.AI coding plan to OpenCode, it stores the API key, and AI Status reads that key to call Z.AI's usage API. Set it up once in OpenCode and you're done.

You can also supply `ZAI_API_KEY` directly to the AI Status process without OpenCode.

## Requirements

- `ZAI_API_KEY`, or **OpenCode** authenticated with your Z.AI coding plan
- `jq` and `curl` (already required by AI Status)

## Step 1 — Add Z.AI to OpenCode

Run OpenCode's auth flow and pick **Z.AI** (the coding plan):

```bash
opencode auth login
```

OpenCode saves the credential in:

```
~/.local/share/opencode/account.json
```

AI Status finds the account whose `serviceID` is `zai-coding-plan` (or `zai`) and reads its `credential.key`.

## Step 2 — Enable it in AI Status

Right-click the AI Status module to open the config TUI, make sure **Z.AI** is enabled, then left-click to refresh.

## What it tracks

Rolling, weekly, and monthly usage, each with a reset timer.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Shows nothing / `success: false` | No Z.AI account in OpenCode — run `opencode auth login` and add your Z.AI coding plan. |
| Confirm the key exists | `jq '.accounts[] \| select(.serviceID \| test("zai"))' ~/.local/share/opencode/account.json` |
| Blank after a while | Re-authenticate Z.AI in OpenCode to refresh the key. |

Run the provider's fetch script by hand to see the raw response:

```bash
bash ~/.local/share/ai-status/packages/lib/src/providers/zai/query.sh
```

## Multiple accounts

Set `auth_file` to that account's OpenCode `account.json`, or map `ZAI_API_KEY` to its own environment variable. There is no application-imposed account limit. See the [authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).
