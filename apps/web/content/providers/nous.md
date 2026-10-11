Nous Research’s Portal offers subscription credits and optional purchased credits. AI Status reads that account’s OAuth billing data, showing the remaining allowance separately from top-ups. It requires an existing authorized session; AI Status does not start the Portal sign-in flow.

## Requirements

- A Nous Portal account with subscription or credit data available.
- A current OAuth **access token**, supplied through `NOUS_ACCESS_TOKEN` or an explicitly selected compatible JSON credential file.
- Connectivity to `portal.nousresearch.com` and an installed AI Status integration.

## Step 1 — Authorize the Portal account

Check your account at [Nous Portal subscription management](https://portal.nousresearch.com/manage-subscription). The official [Nous Portal guide](https://hermes-agent.nousresearch.com/docs/integrations/nous-portal) documents `hermes setup --portal`, which stores a refresh token. That command alone does **not** provide compatible AI Status credentials. Without another authorized client or source providing a current access token, this integration cannot be configured yet.

AI Status does not exchange refresh tokens or renew sessions. Your source must contain a supported current access-token field.

## Step 2 — Reference the credentials

CLI examples use `ai-status` on Linux/macOS, or `~/.local/bin/ai-status` if unavailable on PATH. Windows uses the packaged `.\ai-status-cli.exe` from its folder, or its full path.

Provide `NOUS_ACCESS_TOKEN` to AI Status. For two accounts, reference variables already containing their current tokens:

```bash
ai-status accounts add nous --id nous-personal --label Personal --env NOUS_ACCESS_TOKEN=NOUS_PERSONAL_SESSION
ai-status accounts add nous --id nous-work --label Work --env NOUS_ACCESS_TOKEN=NOUS_WORK_SESSION
ai-status accounts list
```

As an alternative to the environment mapping, select a compatible OAuth JSON file. Choose one method for `nous-work`:

```bash
ai-status accounts add nous --id nous-work --label Work --auth-file /path/to/work/nous-oauth.json
```

The collector accepts `access_token` at the top level, or `nous.access_token` inside a `nous` object. It does not automatically discover `~/.hermes/auth.json`; selecting a refresh-token-only file will not work. Use an absolute Windows path on Windows. Connections have independent sources and no account-count limit. See the [multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

## Step 3 — Enable the connection

On Linux Waybar, right-click the module or run `ai-status config`. In Omarchy Quickshell, Windows, and macOS, open **Settings** from the usage panel. Enable **Nous Research** for the default token or enable the labeled saved connections. Save, then refresh the panel or run `ai-status refresh`.

Desktop apps need inherited variables or a file containing a current compatible access token.

## What it tracks

The collector reads `/api/oauth/account`. **Subscription credits remaining** uses the reported allowance balance. When a positive monthly allowance is also present, **Monthly subscription credits used** is calculated as allowance minus remaining credits and gets a percentage. A reset countdown appears when the account response supplies its period end.

**Purchased credits remaining** and **Total usable credits** appear when reported; the plan label is also retained when available. Units are **credits**, without inventing a USD exchange rate. Top-up credits and subscription consumption remain separate metrics.

## Limits and troubleshooting

The integration has no per-model spending report or local Hermes activity counter. Missing subscription fields do not mean a zero allowance. Session renewal remains the responsibility of the authorized client.

| Symptom | What to check |
|---|---|
| No credentials | Set NOUS_ACCESS_TOKEN or explicitly select a compatible auth_file. |
| Works initially, then expires | Renew authorization in the owning client and update the access-token source. |
| Hermes login succeeds, AI Status fails | Check that the selected file contains a current supported access_token, not only a refresh token. |
| No monthly percentage | The response must include remaining credits and a positive monthly allowance. |
| No purchased-credit row | This field appears only when reported by the account service. |
