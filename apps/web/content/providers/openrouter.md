## OpenRouter

Tracks key usage, monthly spend, remaining limit and prepaid credits.

Authentication: **OPENROUTER_API_KEY**. Enable `openrouter` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Account credit balances require `OPENROUTER_MANAGEMENT_KEY`. A regular `OPENROUTER_API_KEY` reads only that key's usage and limits. The optional `include_credits` account option requests credits and requires a management key; supplying a management key already enables credit collection.
