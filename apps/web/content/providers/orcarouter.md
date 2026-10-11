OrcaRouter routes API requests through an account with billing usage and spending limits. AI Status combines its reported cumulative spend with an applicable credit limit to show both consumption and the calculated funds remaining.

## Requirements

An OrcaRouter account and API key that can access its dashboard billing endpoints; connectivity to `api.orcarouter.ai`. Use an installed AI Status desktop integration or its CLI. Credentials must be available to the process performing collection.

## Step 1 — Obtain the credential

Sign in through the [OrcaRouter website](https://www.orcarouter.ai/) and create an API key in the dashboard. Check the account’s billing context before connecting it; its [pricing and billing page](https://www.orcarouter.ai/pricing) describes the available ways to fund usage.

## Step 2 — Configure the connection

Make the key available as `ORCAROUTER_API_KEY` or reference a private key file in an explicit connection. AI Status requests `/v1/dashboard/billing/usage` and `/v1/dashboard/billing/subscription` for that credential.

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

For two accounts, map independent source variables that already contain their credentials:

```bash
ai-status accounts add orcarouter --id orcarouter-personal --label Personal --env ORCAROUTER_API_KEY=ORCAROUTER_PERSONAL_CREDENTIAL
ai-status accounts add orcarouter --id orcarouter-work --label Work --env ORCAROUTER_API_KEY=ORCAROUTER_WORK_CREDENTIAL
ai-status accounts list
```

Alternatively, use a private file reference for desktop launches. Choose this or the environment mapping for the work connection. Save as `connection.json`, adapt the path, then run `ai-status accounts add --file connection.json`:

```json
{
  "id": "orcarouter-work",
  "provider": "orcarouter",
  "label": "Work",
  "env": {
    "ORCAROUTER_API_KEY": {
      "from_file": "/path/to/private-credentials/orcarouter-work-key"
    }
  }
}
```

The file contains the key; the connection saves its path. Use an absolute path appropriate to your OS. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md) for unlimited connections and source options.

## Step 3 — Enable and refresh

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, or macOS, open the usage panel’s **Settings**. Enable **OrcaRouter** for the default credential, or enable your labeled saved connections, save, then refresh the panel or run `ai-status refresh`.

Environment changes reach apps launched from that environment; relaunch if needed.

## What it tracks

**Cumulative spend** is total_usage converted from cents to USD. The collector uses the first numeric hard_limit_usd, soft_limit_usd, or system_hard_limit_usd returned by the subscription response as its candidate limit. Only a positive, non-sentinel candidate is shown as an applicable limit. When valid, spend gets a percentage and **Remaining credit balance** is calculated as that limit minus cumulative spend.

## Limits and troubleshooting

This is cumulative spending, with no claim that the counter resets each calendar month. The remaining-credit row is calculated from the reported limit and spend; it is not a separately queried wallet balance. If the candidate limit is missing or unusable, AI Status shows spend without inventing remaining funds or a percentage. No model-level costs, token counts, or reset times are collected.

| Symptom | What to check |
|---|---|
| Missing key | Check ORCAROUTER_API_KEY or the connection’s referenced key file. |
| Inference succeeds, dashboard billing fails | Verify this key’s account and dashboard billing access with OrcaRouter. |
| Spend appears without remaining balance | The response did not provide a usable applicable limit. |
| Remaining amount differs from wallet view | This row is limit minus cumulative spend; reconcile the limit and counter in dashboard billing. |

If a request is rate-limited, allow the displayed cooldown to finish. A cached result can remain visible with an error marker; refreshing does not bypass the provider’s wait.
