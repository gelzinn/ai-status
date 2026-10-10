## OpenAI API

Tracks monthly organization api spend.

Authentication: **OPENAI_ADMIN_KEY (organization Admin key)**. Enable `openai-api` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Use an organization Admin key. Project inference keys and Codex OAuth tokens cannot query organization costs. Optional `project_ids` scopes costs; `monthly_budget` is your own monitoring budget.
