## Google Cloud

Tracks project quotas; optional billing-export monthly cost.

Authentication: **gcloud or GOOGLE_CLOUD_ACCESS_TOKEN; project_id option**. Enable `google-cloud` in Settings after configuring credentials. New integrations are opt-in.

Each connection can have a separate label, credential source and provider options. Add accounts with `ai-status accounts add --file connection.json`; inspect `ai-status accounts list`. See the [complete authentication and multiple-account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md).

Only percentages with a reported limit (or an explicitly configured budget) display a progress bar. Balance and cost metrics display their amount and currency. Upstream availability depends on your account and permissions.

Set `options.project_id`. Monitoring Viewer permissions are required for quota metrics. Optional `billing_table` selects an existing BigQuery Cloud Billing export and requires BigQuery read/query permissions; these queries can incur BigQuery charges. Export delays apply.
