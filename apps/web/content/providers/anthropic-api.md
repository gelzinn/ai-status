## Anthropic API

Tracks monthly organization API spend.

Authentication: **ANTHROPIC_ADMIN_KEY (admin-compatible Console key) or ANTHROPIC_ADMIN_TOKEN (org:admin OAuth)**. Enable `anthropic-api` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Workspace-scoped inference keys cannot query the organization costs API. Use a Claude Console Admin API key, an unscoped personal/service account key with admin access, or an `org:admin` OAuth token; amounts are reported as USD spend for the current UTC month.
