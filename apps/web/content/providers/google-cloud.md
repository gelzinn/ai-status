AI Status monitors Google Cloud quota usage for a project and can show current-month spend from an existing BigQuery billing export. It helps watch Vertex AI or other service capacity alongside costs. Quota units and billing currency are separate metrics; neither is a prepaid balance.

## Requirements

- A project ID and Cloud Monitoring time-series read permissions through a suitable [Monitoring IAM role](https://cloud.google.com/monitoring/access-control).
- Google Cloud CLI authentication, or `GOOGLE_CLOUD_ACCESS_TOKEN` supplied to AI Status.
- For costs: an existing [Cloud Billing export](https://cloud.google.com/billing/docs/how-to/export-data-bigquery), table-read permissions, and permission to run BigQuery jobs in the query project.

## Set up project monitoring

1. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install), run `gcloud auth login`, and authorize the intended account. AI Status calls `gcloud auth print-access-token`; it does not directly read service-account JSON simply because `GOOGLE_APPLICATION_CREDENTIALS` is set.
2. Set `options.project_id`, or `GOOGLE_CLOUD_PROJECT` (`GCLOUD_PROJECT` is accepted too). Optionally set `gcloud_account` to the authorized account email. Named connections require a token, explicit `CLOUDSDK_CONFIG`, or `gcloud_account`; they never silently use the default account.
3. Narrow quotas with `service`, such as `aiplatform.googleapis.com`, and optionally `quota_metric`. See [Chart and monitor quota metrics](https://cloud.google.com/monitoring/alerts/using-quota-metrics) for available series.
4. For costs, set `billing_table` to `project.dataset.table`. `billing_project_id` selects the BigQuery job project; `billing_location` sets location. Spend stays scoped to `project_id` unless `billing_all_projects: true` is explicit. `service_id` narrows billing services. With `billing_table`, quotas default off; set `include_quotas: true` for both.
5. Enable **Google Cloud** in Linux Quickshell **Settings** or `ai-status config` for Waybar. Windows users open tray **Settings** and **Save**; macOS users open menu bar **Settings** and **Save**. Choose **Refresh**, or `ai-status refresh` (`.\ai-status-cli.exe refresh` on Windows).

## Separate development and production

Save `google-production.json`, replacing account and project/table names:

```json
{
  "id": "google-production",
  "provider": "google-cloud",
  "label": "Production cloud",
  "env": {
    "CLOUDSDK_CONFIG": {"from_env": "GOOGLE_WORK_GCLOUD_CONFIG"}
  },
  "options": {
    "gcloud_account": "your-authorized-account@example.com",
    "project_id": "your-production-project",
    "billing_table": "your-export-project.billing.your_export_table",
    "billing_project_id": "your-query-project",
    "billing_location": "US",
    "include_quotas": true,
    "service": "aiplatform.googleapis.com",
    "maximum_bytes_billed": 1000000000,
    "monthly_budget": 500,
    "budget_currency": "USD"
  }
}
```

Set `GOOGLE_WORK_GCLOUD_CONFIG` to your existing work gcloud configuration directory, then import with `ai-status accounts add --file google-production.json`; Windows uses `.\ai-status-cli.exe`. Create a development connection with another ID and project. For isolated gcloud configurations, map `CLOUDSDK_CONFIG` to an environment variable pointing at that configuration directory. Token connections can map `GOOGLE_CLOUD_ACCESS_TOKEN` to an account-specific variable or file, renewed on expiry. See the [account guide](https://github.com/gelzinn/ai-status/blob/main/packages/lib/PROVIDERS.md#multiple-accounts-and-connections).

On Windows, run `.\ai-status-cli.exe` from the AI Status application folder or use its full path; it may not be on your terminal PATH.

On macOS, use `~/.local/bin/ai-status` if `ai-status` is not on PATH; the same full-path fallback works for a standard Linux install.

## What the metrics mean

Allocation gauges match limits by project, service, quota metric, and location. Rate quotas also require compatible limit/window labels. Missing or ambiguous limits leave usage as quota units without a percentage. These are recent observations, not remaining monthly tokens.

Billing sums exported costs plus credits by usage time within the UTC month, keeping currencies separate. Export delays apply; missing rows do not become zero. A positive `monthly_budget` adds a local comparison only for matching `budget_currency`. BigQuery queries can incur charges: caching is enabled and `maximum_bytes_billed` defaults to one billion bytes. The countdown marks the next UTC month.

## Troubleshooting

| Symptom | What to check |
|---|---|
| 401 / expired token | Renew the token or sign in again with gcloud. |
| 403 from Monitoring | Check time-series read permissions and project. |
| No quota rows | Verify filters and whether compatible quota series are exported. |
| BigQuery fails | Check schema, dataset location, table-read/job permissions, and `maximum_bytes_billed`. |
| Spend too broad | Check `project_id` and `billing_all_projects`; the job project is separate. |
| Recent spend missing | Check export freshness before treating it as a billing error. |
