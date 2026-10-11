AI Status monitors an OpenRouter key's spend and limits, or the account's total credits and remaining balance. A key cap describes what that key may spend; account credits describe funds shared by the account's keys.

## Requirements

- An [OpenRouter account](https://openrouter.ai/).
- `OPENROUTER_API_KEY` for that key's usage, and/or `OPENROUTER_MANAGEMENT_KEY` for account credits.
- AI Status on Linux, Windows, or macOS.

A management key alone provides account metrics. Providing a regular key too collects its usage. Management keys cannot make completion requests; see [Management API keys](https://openrouter.ai/docs/guides/overview/auth/management-api-keys).

## Choose credentials and connect

1. For individual key spend, open [API keys](https://openrouter.ai/settings/keys) and create or choose a regular key. Supply it as `OPENROUTER_API_KEY`.
2. For account balance, follow the [management-key creation guide](https://openrouter.ai/docs/guides/overview/auth/management-api-keys). Supply that credential as `OPENROUTER_MANAGEMENT_KEY`. A regular key does not gain account-credit permissions through the legacy `include_credits` option.
3. Save a connection using environment or credential-file references. For default connections, variables must reach the desktop/daemon process; exporting in an unrelated terminal does not update an already running app.
4. Enable **OpenRouter** in Settings. On Linux, use Quickshell **Settings** or `ai-status config` for Waybar. On Windows, open tray **Settings** and **Save**; on macOS use menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes with a left-click; CLI users run `ai-status refresh` (`.\ai-status-cli.exe refresh` on Windows).

## Keep personal and work credits separate

These commands reference existing environment variables. Values on the right are variable names, not literal keys:

```bash
ai-status accounts add openrouter --id personal-credits --label Personal --env OPENROUTER_MANAGEMENT_KEY=OPENROUTER_PERSONAL_MANAGEMENT_KEY
ai-status accounts add openrouter --id work-credits --label Work --env OPENROUTER_MANAGEMENT_KEY=OPENROUTER_WORK_MANAGEMENT_KEY
```

For desktop startup, use `ai-status accounts add --file connection.json` with a reference such as `"OPENROUTER_MANAGEMENT_KEY": {"from_file": "/path/to/private/work-management-key"}` inside `env`. Give the definition its own `id`, `provider: "openrouter"`, and `label`. Windows uses `.\ai-status-cli.exe`. Each connection keeps its own scope and cache. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On Windows, run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; it may not be on your terminal PATH.

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## Read the metrics correctly

Key metrics can include capped spend, separately reported monthly spend, an effective organization budget, and free-model daily request counts when returned by OpenRouter. Without a positive limit, spend has no bar. Duplicate monthly cap/spend values are consolidated.

Account metrics use the [credits endpoint](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits). **$25 / $100** means $25 spent against $100 total credits, leaving **$75** available. Remaining balance appears in account-credit detail, or as an amount metric when a ratio is unavailable. It is never calculated by subtracting one key's spend from account credits. Credit consumption is not a monthly reset quota.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Spend appears, balance does not | Add `OPENROUTER_MANAGEMENT_KEY`; a regular key supplies key metrics. |
| 401 or 403 with management credentials | Check validity and account ownership of the management key. |
| Key spend differs from account spend | Account usage includes all keys; compare matching scopes. |
| No bar for an unlimited key | There is no positive reported cap; the amount remains meaningful. |
| 429 / cached data | Wait for the retry cooldown; management-key failures follow normal cache and cooldown handling. |
