Novita account credits support its cloud services. AI Status reads the billing balance so you can monitor available funds alongside any cash-balance and outstanding-invoice amounts included in the response.

## Requirements

A Novita account, its API key, and access to the Novita billing API at `api.novita.ai`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in to the [Novita console](https://novita.ai/console). Open API Keys / Key Management and create a key for the account you want to monitor. The console also links to Billing for checking the same account’s funds.

## Step 2 — Configure the connection

Supply `NOVITA_API_KEY` to AI Status or use a saved connection with an environment or file reference. This integration queries `/openapi/v1/billing/balance/detail` and does not need a running inference client.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add novita --id novita-personal --label Personal --env NOVITA_API_KEY=NOVITA_PERSONAL_CREDENTIAL
ai-status accounts add novita --id novita-work --label Work --env NOVITA_API_KEY=NOVITA_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "novita-work",
  "provider": "novita",
  "label": "Work",
  "env": {
    "NOVITA_API_KEY": {
      "from_file": "/path/to/private-credentials/novita-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Novita** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Available credit balance** is the provider’s availableBalance expressed in USD. **Cash balance** and **Outstanding invoices** appear separately when Novita includes them. The collector converts the API’s monetary units by dividing by 10,000, so the displayed amount is currency rather than the raw integer. Outstanding invoices describe a billing obligation and should not be read as spendable credit.

## Limits and troubleshooting

This collector does not query Novita’s monthly bill or usage-detail endpoints. It therefore provides no current-month spend, service breakdown, token count, or quota reset. The balance snapshot is not a prediction of how long credits will last. Cash and available balances may differ because they represent separate billing fields; AI Status does not calculate its own wallet total by combining them.

| Symptom | What to check |
|---|---|
| No credential | Ensure NOVITA_API_KEY is visible to the app or configure the key file reference. |
| Billing request rejected | Confirm the account/key context in Novita and its ability to read billing data. |
| Amount differs from raw response | Billing values are scaled by 10,000 before display; compare currency amounts. |
| Missing cash or invoice row | Those rows appear only when returned; an absent field is not assumed to be zero. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
