AI Status uses your configured OpenRouter key to read its spend and limits and query the account's total credits and remaining balance. When the account lookup succeeds, a progress bar shows consumed credits against total credits, with the available balance below. A key cap describes what that key may spend; account credits describe funds shared by the account's keys.

## Requirements

- An [OpenRouter account](https://openrouter.ai/).
- `OPENROUTER_API_KEY` for key usage and the account-credit lookup.
- AI Status on Linux, Windows, or macOS.

An existing `OPENROUTER_MANAGEMENT_KEY` is an optional override for account credits; it can also provide account metrics on its own. AI Status always attempts the lookup with the configured credential, but the [credits API documentation](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits) still requires management-key permissions. A rejected lookup keeps valid key usage visible instead of guessing a balance.

## Choose credentials and connect

1. Open [API keys](https://openrouter.ai/settings/keys) and choose the key you already use. Supply it as `OPENROUTER_API_KEY`.
2. AI Status queries both key usage and account credits with that key. No separate key or `include_credits` option is needed to attempt the account lookup. If a management credential is already configured, it takes precedence for account credits.
3. Save a connection using environment or credential-file references. For default connections, variables must reach the desktop/daemon process; exporting in an unrelated terminal does not update an already running app.
4. Enable **OpenRouter** in Settings. On Linux, use Quickshell **Settings** or `ai-status config` for Waybar. On Windows, open tray **Settings** and **Save**; on macOS use menu bar **Settings** and **Save**. Choose **Refresh**. Waybar also refreshes with a left-click; CLI users run `ai-status refresh` (`.\ai-status-cli.exe refresh` on Windows).

## Keep personal and work credits separate

These commands reference existing environment variables. Values on the right are variable names, not literal keys:

```bash
ai-status accounts add openrouter --id personal-credits --label Personal --env OPENROUTER_API_KEY=OPENROUTER_PERSONAL_KEY
ai-status accounts add openrouter --id work-credits --label Work --env OPENROUTER_API_KEY=OPENROUTER_WORK_KEY
```

For desktop startup, use `ai-status accounts add --file connection.json` with a reference such as `"OPENROUTER_API_KEY": {"from_file": "/path/to/private/work-api-key"}` inside `env`. Give the definition its own `id`, `provider: "openrouter"`, and `label`. Windows uses `.\ai-status-cli.exe`. Each connection keeps its own scope and cache. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On Windows, run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; it may not be on your terminal PATH.

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## Read the metrics correctly

Key metrics can include capped spend, separately reported monthly spend, an effective organization budget, and free-model daily request counts when returned by OpenRouter. Without a positive limit, spend has no bar. Duplicate monthly cap/spend values are consolidated.

Account metrics use the [credits endpoint](https://openrouter.ai/docs/api/api-reference/credits/get-remaining-credits). **$25 / $100** means $25 spent against $100 total credits, leaving **$75** available. Remaining balance appears in account-credit detail, or as an amount metric when a ratio is unavailable. It is never calculated by subtracting one key's spend from account credits. Credit consumption is not a monthly reset quota.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Spend appears with “Account balance unavailable for this key” | OpenRouter denied this key's account-credit lookup. Check the credential's permissions; key spend remains valid. |
| 401 or 403 with management credentials | Check validity and account ownership of the management key. |
| Key spend differs from account spend | Account usage includes all keys; compare matching scopes. |
| No bar for an unlimited key | There is no positive reported cap; the amount remains meaningful. |
| 429 / cached data | Wait for the retry cooldown; account-credit failures follow normal cache and cooldown handling. |
