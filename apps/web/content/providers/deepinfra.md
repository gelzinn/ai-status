DeepInfra combines a prepaid account balance with a separate current-month spending view. AI Status collects both, making it useful for checking funds on hand while following the cost of your hosted inference workloads.

## Requirements

A DeepInfra account with a valid API token; access to `api.deepinfra.com`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Open the [DeepInfra API keys dashboard](https://deepinfra.com/dash/api_keys), sign in, and create or copy a token for the account you want to track.

## Step 2 — Configure the connection

Make the token available as `DEEPINFRA_API_KEY`. Other tools may call their token variable something else; map that existing variable to this credential name in an explicit AI Status connection.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add deepinfra --id deepinfra-personal --label Personal --env DEEPINFRA_API_KEY=DEEPINFRA_PERSONAL_CREDENTIAL
ai-status accounts add deepinfra --id deepinfra-work --label Work --env DEEPINFRA_API_KEY=DEEPINFRA_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "deepinfra-work",
  "provider": "deepinfra",
  "label": "Work",
  "env": {
    "DEEPINFRA_API_KEY": {
      "from_file": "/path/to/private-credentials/deepinfra-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **DeepInfra** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Available prepaid balance** comes from the payment checklist, accounting for its reported recent charges. **Current-month spend** comes from the usage report for the current UTC calendar month. Spend is converted from cents to USD; a positive reported spending limit supplies a percentage for that spend row. If the report has no matching month, only the balance is shown.

## Limits and troubleshooting

The collector reads `/payment/checklist` and `/payment/usage`; it does not estimate charges from request counts. The balance and month’s spend describe different things and should not be added together. No per-model breakdown or monthly reset timestamp is collected. The account billing dashboard remains the place to reconcile invoices or a provider-side reporting delay.

| Symptom | What to check |
|---|---|
| No credential | Make DEEPINFRA_API_KEY accessible to the process or configure a file reference. |
| Token works elsewhere, balance fails | Check this account’s billing access and whether both payment endpoints are reachable. |
| Only balance appears | The report may contain no row for the current UTC month; this does not imply zero spending. |
| Month differs from local date | Month selection uses UTC, especially around midnight on a month boundary. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
