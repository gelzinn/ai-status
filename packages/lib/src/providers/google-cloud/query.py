"""Cloud Monitoring quotas or optional net costs from a billing BigQuery export."""
from datetime import timedelta
import os
import re
from urllib.parse import quote

from core.metered import iso_time, json_request, month_window, options
from core.provider_http import QueryError, cli_path, output, require_token, run_cli

METRIC_PREFIX = "serviceruntime.googleapis.com/quota/"


def _token(opts):
    token = os.environ.get("GOOGLE_CLOUD_ACCESS_TOKEN")
    if token:
        return token
    if os.environ.get("AI_STATUS_ACCOUNT_ID") and not (os.environ.get("CLOUDSDK_CONFIG") or opts.get("gcloud_account")):
        raise QueryError("Named Google Cloud accounts require GOOGLE_CLOUD_ACCESS_TOKEN, an explicit CLOUDSDK_CONFIG, or options.gcloud_account; the default gcloud account is not used.")
    args = [cli_path("gcloud"), "auth", "print-access-token", "--quiet"]
    if opts.get("gcloud_account"):
        args.append("--account=" + str(opts["gcloud_account"]))
    return require_token(run_cli(args).strip(), "Sign in with gcloud auth login or set GOOGLE_CLOUD_ACCESS_TOKEN.")


def _series(project, headers, kind, start, now, opts):
    filter_ = f'metric.type="{METRIC_PREFIX}{kind}" resource.type="consumer_quota"'
    # JSON quoting escapes quotes/backslashes in Monitoring filter values.
    import json
    if opts.get("service"):
        filter_ += ' resource.labels.service=' + json.dumps(str(opts["service"]))
    if opts.get("quota_metric"):
        filter_ += ' metric.labels.quota_metric=' + json.dumps(str(opts["quota_metric"]))
    params = {"filter": filter_, "interval.startTime": iso_time(start), "interval.endTime": iso_time(now),
              "view": "FULL", "pageSize": 1000}
    result, seen = [], set()
    for _ in range(100):
        data = json_request(f"https://monitoring.googleapis.com/v3/projects/{quote(project, safe='')}/timeSeries", headers, params)
        if not isinstance(data, dict) or not isinstance(data.get("timeSeries", []), list):
            raise QueryError("Cloud Monitoring returned an invalid time-series response.")
        result.extend(data.get("timeSeries", []))
        token = data.get("nextPageToken")
        if not token:
            return result
        if not isinstance(token, str) or token in seen:
            raise QueryError("Cloud Monitoring pagination is incomplete; retry later.")
        seen.add(token)
        params["pageToken"] = token
    raise QueryError("Too many Cloud Monitoring pages; configure a service or quota_metric filter.")


def _billing(project, headers, opts, start, now):
    table = opts["billing_table"]
    if not isinstance(table, str) or not re.fullmatch(r"[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_-]+", table):
        raise QueryError("billing_table must be project.dataset.table for a standard or detailed Cloud Billing export.")
    maximum = opts.get("maximum_bytes_billed", 1000000000)
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum <= 0:
        raise QueryError("maximum_bytes_billed must be a positive integer.")
    sql = ("SELECT currency, SUM(CAST(cost AS NUMERIC)) + "
           "SUM(IFNULL((SELECT SUM(CAST(c.amount AS NUMERIC)) FROM UNNEST(credits) c), 0)) AS amount "
           f"FROM `{table}` WHERE usage_start_time >= @start AND usage_start_time < @end")
    parameters = [{"name": "start", "parameterType": {"type": "TIMESTAMP"}, "parameterValue": {"value": iso_time(start)}},
                  {"name": "end", "parameterType": {"type": "TIMESTAMP"}, "parameterValue": {"value": iso_time(now)}}]
    # project_id is both the default monitored project and the billing scope;
    # billing_project_id controls where the query job executes, not the spend scope.
    if not opts.get("billing_all_projects"):
        sql += " AND project.id = @project"
        parameters.append({"name": "project", "parameterType": {"type": "STRING"}, "parameterValue": {"value": project}})
    if opts.get("service_id"):
        sql += " AND service.id = @service"
        parameters.append({"name": "service", "parameterType": {"type": "STRING"}, "parameterValue": {"value": str(opts["service_id"])}})
    sql += " GROUP BY currency"
    billing_project = str(opts.get("billing_project_id") or project)
    url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{quote(billing_project, safe='')}/queries"
    body = {"query": sql, "useLegacySql": False, "parameterMode": "NAMED", "queryParameters": parameters,
            "maximumBytesBilled": str(maximum), "timeoutMs": 3000, "maxResults": 1000, "useQueryCache": True}
    if opts.get("billing_location"):
        body["location"] = str(opts["billing_location"])
    response = json_request(url, headers, method="POST", data=body)
    rows, seen = [], set()
    # BigQuery jobs.query can return before completion. Read its query results,
    # retaining server-issued project/location IDs and every result page.
    for _ in range(12):
        if not isinstance(response, dict) or response.get("errors"):
            raise QueryError("BigQuery billing query failed; check export schema, IAM access, location and maximum_bytes_billed.")
        if response.get("jobComplete"):
            page_rows = response.get("rows", [])
            if not isinstance(page_rows, list):
                raise QueryError("BigQuery returned invalid billing rows.")
            rows.extend(page_rows)
            token = response.get("pageToken")
            if not token:
                return rows
            if not isinstance(token, str) or token in seen:
                raise QueryError("BigQuery billing result pagination is incomplete.")
            seen.add(token)
        else:
            token = None
        job = response.get("jobReference") or {}
        if not isinstance(job, dict) or not job.get("jobId"):
            raise QueryError("BigQuery billing query is incomplete; retry later.")
        params = {"timeoutMs": 1000, "maxResults": 1000}
        if job.get("location"):
            params["location"] = job["location"]
        if token:
            params["pageToken"] = token
        project_name = quote(str(job.get("projectId") or billing_project), safe="")
        job_name = quote(str(job["jobId"]), safe="")
        response = json_request(f"https://bigquery.googleapis.com/bigquery/v2/projects/{project_name}/queries/{job_name}", headers, params)
    raise QueryError("BigQuery billing query did not finish; retry later or narrow the billing scope.")


def query():
    opts = options()
    project = opts.get("project_id") or os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCLOUD_PROJECT")
    if not isinstance(project, str) or not project:
        raise QueryError("Configure options.project_id or GOOGLE_CLOUD_PROJECT for Google Cloud monitoring.")
    headers = {"Authorization": f"Bearer {_token(opts)}"}
    start, now, end = month_window()
    result = {"_ai_status": {"project_id": project, "reset_at": iso_time(end),
              "monthly_budget": opts.get("monthly_budget"), "budget_currency": opts.get("budget_currency", "USD")}}
    if opts.get("billing_table"):
        result["billing_rows"] = _billing(project, headers, opts, start, now)
    if opts.get("include_quotas", not bool(opts.get("billing_table"))):
        # Gauge limit samples arrive once per day; allocation usage can repeat
        # once per day. A 48-hour lookup retrieves the latest observed gauges.
        for kind in ("allocation/usage", "limit", "ratev2/net_usage", "ratev2/limit"):
            lookback = timedelta(minutes=10) if kind == "ratev2/net_usage" else timedelta(hours=48)
            result[kind] = _series(project, headers, kind, now - lookback, now, opts)
    return result


def main():
    output(query)


if __name__ == "__main__":
    main()
