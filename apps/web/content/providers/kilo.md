## Kilo

Tracks personal or organization credit balance.

Authentication: **KILO_API_KEY; optional organization_id**. Enable `kilo` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.
