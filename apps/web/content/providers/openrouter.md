## OpenRouter

Tracks key usage and limits, account spend / total credits, and the remaining account balance.

Authentication: **OPENROUTER_API_KEY** for key usage; **OPENROUTER_MANAGEMENT_KEY** for account credits. Enable `openrouter` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Account credits require a [management key](https://openrouter.ai/docs/guides/overview/auth/management-api-keys). A management key alone is enough to show account metrics. For example, **$25.00 / $100.00** means $25 spent out of $100 total account credits, with **$75.00** remaining shown separately. Providing both keys also shows the regular key's usage and limits.

A regular API key keeps working without management credentials and shows guidance for enabling account credits. The legacy `include_credits` option does not grant account permissions. Configured management-key authentication or rate-limit failures retain cached data and respect retry cooldowns.
