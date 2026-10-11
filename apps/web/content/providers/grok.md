The Grok API integration reads an xAI team’s prepaid API credits. It uses a management credential because billing lives in the Management API; a regular inference key is a different credential type.

## Requirements

An xAI Console team and a management key that can read its prepaid billing balance. Organization-scoped keys also need the target team ID. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Open the [xAI Console](https://console.x.ai/) and create a key in Management Keys. Follow the official [Management API setup](https://docs.x.ai/developers/rest-api-reference/management); if management-key controls are unavailable, ask your team administrator for access.

## Step 2 — Configure the connection

Provide `XAI_MANAGEMENT_KEY`. For an organization-scoped key, set `"team_id": "YOUR_XAI_TEAM_ID"` in the connection’s `options`. A team-scoped key can resolve its team through management-key validation when team_id is omitted.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add grok --id grok-personal --label Personal --env XAI_MANAGEMENT_KEY=GROK_PERSONAL_CREDENTIAL
ai-status accounts add grok --id grok-work --label Work --env XAI_MANAGEMENT_KEY=GROK_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "grok-work",
  "provider": "grok",
  "label": "Work",
  "env": {
    "XAI_MANAGEMENT_KEY": {
      "from_file": "/path/to/private-credentials/grok-work-key"
    }
  },
  "options": {
    "team_id": "YOUR_XAI_TEAM_ID"
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Grok API (xAI)** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Prepaid API credit balance** is the USD balance from `/v1/billing/teams/{team_id}/prepaid/balance`. The collector converts the service’s signed cents balance into the displayed remaining-credit amount. This is team billing scope, rather than the usage of one inference key. See the [billing reference](https://docs.x.ai/developers/rest-api-reference/management/billing) for the underlying management service.

## Limits and troubleshooting

This integration does not track a consumer Grok subscription, SuperGrok allowance, or Grok Bot weekly usage. It does not fetch invoice totals, monthly spending, per-model charges, or rate-limit windows. A prepaid amount has no percentage or automatic reset timer. The [API authentication overview](https://docs.x.ai/developers/rest-api-reference/inference) distinguishes inference and management credentials.

| Symptom | What to check |
|---|---|
| Inference works, balance does not | Use XAI_MANAGEMENT_KEY, not the regular inference API key. |
| Requested team_id | Set the target team ID for an organization-scoped management key. |
| Team balance rejected | Confirm team_id and the key’s billing access with your administrator. |
| Subscription credits missing | Use the appropriate subscription integration; this row is API team prepaid credit. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
