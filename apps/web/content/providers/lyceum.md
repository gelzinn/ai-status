Lyceum offers hosted AI workloads and an account billing balance. AI Status displays the USD credits available and the credits used in the period Lyceum reports, helping you distinguish remaining funds from consumption.

## Requirements

A Lyceum account, an API key for that account, and connectivity to `api.lyceum.technology`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in to the [Lyceum API keys dashboard](https://dashboard.lyceum.technology/api-keys) and generate a key. This is the key location identified by [Lyceum’s API authentication reference](https://docs.lyceum.technology/api-reference/workload-management/abort-execution).

## Step 2 — Configure the connection

Provide `LYCEUM_API_KEY` or configure a connection referencing an existing variable or a private key file. AI Status uses it as a bearer credential for `/api/v2/external/billing/credits`.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add lyceum --id lyceum-personal --label Personal --env LYCEUM_API_KEY=LYCEUM_PERSONAL_CREDENTIAL
ai-status accounts add lyceum --id lyceum-work --label Work --env LYCEUM_API_KEY=LYCEUM_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "lyceum-work",
  "provider": "lyceum",
  "label": "Work",
  "env": {
    "LYCEUM_API_KEY": {
      "from_file": "/path/to/private-credentials/lyceum-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **Lyceum** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Available balance** displays `available_credits` in USD. **Credits used** displays `used_credits` in USD with the detail **Reported period**. These are distinct rows: one shows funds left, the other shows the consumption counter supplied by Lyceum. The collector deliberately preserves the provider’s period scope rather than labeling it as monthly spending.

## Limits and troubleshooting

No monthly boundary, reset timer, per-model detail, or spending limit is inferred from this response. Credits used has no progress percentage without an applicable reported limit, and this collector does not supply one. For the scope of charges or invoice reconciliation, compare the account’s billing dashboard. It does not measure local GPU use or derive a cost from your machine’s activity.

| Symptom | What to check |
|---|---|
| Missing key | Check LYCEUM_API_KEY and the connection’s source path or variable. |
| Key rejected | Confirm the key belongs to this dashboard account and has not been revoked. |
| Credits used seems higher than this month | The returned period is not assumed to be a calendar month; compare Lyceum’s billing view. |
| Unsupported usage response | Check service availability; changed or missing billing fields remain unavailable instead of becoming zero. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
