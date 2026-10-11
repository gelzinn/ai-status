"""Mock official usage/billing schemas; never call live accounts in tests."""
from datetime import datetime, timezone
from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import ctypes as C
import importlib.util
import json
import os
from pathlib import Path
import unittest
import threading
import urllib.error
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from core import metered, provider_http, render, windows_http

ROOT = Path(__file__).resolve().parents[1] / "src" / "providers"


def load(provider, module):
    spec = importlib.util.spec_from_file_location(provider.replace("-", "_") + "_" + module, ROOT / provider / (module + ".py"))
    instance = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(instance)
    return instance


def costs(value, currency="usd", cents=False, workspace=None):
    row = {"amount": str(value), "currency": currency} if cents else {"amount": {"value": value, "currency": currency}}
    if workspace:
        row["workspace_id"] = workspace
    return {"results": [row]}


def series(amount, quota="compute.googleapis.com/cpus", location="us-central1", **labels):
    return {"resource": {"type": "consumer_quota", "labels": {"project_id": "p", "service": "compute.googleapis.com", "location": location}},
            "metric": {"labels": {"quota_metric": quota, **labels}},
            "points": [{"interval": {"endTime": "2026-10-10T10:00:00Z"}, "value": {"int64Value": str(amount)}}]}


class HelperTests(unittest.TestCase):
    def test_options_and_auth_override(self):
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_OPTIONS": '{"project_id":"p"}', "AI_STATUS_AUTH_FILE": "/tmp/account.json"}):
            self.assertEqual(metered.options(), {"project_id": "p"})
            self.assertEqual(metered.auth_path("/tmp/default.json"), Path("/tmp/account.json"))
        for invalid in ("[]", "null", "oops"):
            with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_OPTIONS": invalid}), self.assertRaises(provider_http.QueryError):
                metered.options()

    def test_amount_requires_finite_real_limit(self):
        self.assertIsNone(metered.amount_metric(40, "USD", "Balance")["percentage"])
        self.assertEqual(metered.amount_metric(40, "USD", "Spend", limit=100)["percentage"], 40)
        for invalid in (None, 0, -1, "NaN", True, "Infinity"):
            self.assertIsNone(metered.amount_metric(40, "USD", "Spend", limit=invalid)["percentage"])

    def test_json_post_and_form(self):
        with patch.object(metered, "request", return_value='{"ok":true}') as request:
            metered.json_request("https://example.invalid", method="POST", data={"query": "SELECT @value"})
            self.assertEqual(request.call_args.kwargs["method"], "POST")
            self.assertEqual(json.loads(request.call_args.kwargs["data"]), {"query": "SELECT @value"})
            self.assertEqual(request.call_args.args[1]["Content-Type"], "application/json")
            metered.json_request("https://example.invalid", {"Content-Type": "application/x-www-form-urlencoded"}, method="POST", data=b"a=b")
            self.assertEqual(request.call_args.kwargs["data"], b"a=b")

    def test_json_rejects_invalid_or_api_error_response(self):
        for raw in ("bad", "null", '{"error":{"message":"secret"}}'):
            with patch.object(metered, "request", return_value=raw), self.assertRaises(provider_http.QueryError) as error:
                metered.json_request("https://example.invalid")
            self.assertNotIn("secret", str(error.exception))

    def test_pagination_retains_every_bucket_and_scope(self):
        pages = [{"data": [costs(1)], "has_more": True, "next_page": "next"}, {"data": [costs(2)], "has_more": False}]
        with patch.object(metered, "request", side_effect=[json.dumps(p) for p in pages]) as request:
            result = metered.paginated("https://example.invalid", {}, {"project_ids[]": ["p1", "p2"]})
        self.assertEqual(len(result), 2)
        params = parse_qs(urlsplit(request.call_args.args[0]).query)
        self.assertEqual(params["page"], ["next"])
        self.assertEqual(params["project_ids[]"], ["p1", "p2"])

    def test_incomplete_pages_never_become_total(self):
        for page in ({"data": [], "has_more": True}, {"data": [], "has_more": True, "next_page": "same"}):
            with patch.object(metered, "json_request", return_value=page), self.assertRaises(provider_http.QueryError):
                metered.paginated("https://example.invalid", {}, {})

    def test_december_month_boundary(self):
        start, now, end = metered.month_window(datetime(2026, 12, 31, 12, tzinfo=timezone.utc))
        self.assertEqual(metered.iso_time(start), "2026-12-01T00:00:00Z")
        self.assertEqual(metered.iso_time(end), "2027-01-01T00:00:00Z")


class CostProviderTests(unittest.TestCase):
    def test_openai_amounts_are_dollars_separated_by_currency(self):
        parser = load("openai-api", "parse").parse
        result = parser(json.dumps({"data": [costs(1.25), costs(2.5), costs(3, "eur")]}))
        self.assertEqual([(m["unit"], m["amount"]) for m in result["metrics"]], [("EUR", 3), ("USD", 3.75)])
        self.assertTrue(all(m["percentage"] is None for m in result["metrics"]))
        self.assertEqual(len({m["name"] for m in result["metrics"]}), 2)

    def test_anthropic_decimal_cents_and_workspace(self):
        parser = load("anthropic-api", "parse").parse
        result = parser(json.dumps({"data": [costs("123.78912", "USD", True, "chosen"), costs("9999", "USD", True, "other")],
                                    "_ai_status": {"workspace_id": "chosen", "monthly_budget": 10}}))
        metric = result["metrics"][0]
        self.assertAlmostEqual(metric["amount"], 1.2378912)
        self.assertEqual(metric["percentage"], 12.38)
        self.assertIn("configured budget", metric["detail"])

    def test_malformed_costs_not_reported_as_zero(self):
        for provider in ("openai-api", "anthropic-api"):
            parser = load(provider, "parse").parse
            for raw in ("null", "[]", "bad", '{"data":[null]}', '{"data":[{"results":[{"amount":"NaN","currency":"USD"}]}]}'):
                self.assertEqual(parser(raw)["metrics"], [])

    def test_valid_empty_report_is_zero_reported_spend(self):
        self.assertEqual(load("openai-api", "parse").parse('{"data":[]}')["metrics"][0]["amount"], 0)

    def test_admin_key_required_not_inference_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "inference", "ANTHROPIC_API_KEY": "inference"}, clear=True):
            for provider in ("openai-api", "anthropic-api"):
                with self.subTest(provider=provider), self.assertRaises(provider_http.QueryError) as error:
                    load(provider, "query").query()
                self.assertIn("Admin API key", str(error.exception))

    def test_openai_query_project_scope_and_metadata(self):
        query = load("openai-api", "query")
        env = {"OPENAI_ADMIN_KEY": "fake-admin", "AI_STATUS_ACCOUNT_OPTIONS": '{"project_id":"p","monthly_budget":20,"organization_id":"org"}'}
        with patch.dict(os.environ, env, clear=True), patch.object(query, "paginated", return_value=[costs(3)]) as get:
            result = query.query()
        self.assertEqual(get.call_args.args[0], "https://api.openai.com/v1/organization/costs")
        self.assertEqual(get.call_args.args[1]["OpenAI-Organization"], "org")
        self.assertEqual(get.call_args.args[2]["project_ids[]"], ["p"])
        self.assertEqual(result["_ai_status"]["monthly_budget"], 20)

    def test_anthropic_cost_workspace_grouping_not_unsupported_filter(self):
        query = load("anthropic-api", "query")
        with patch.dict(os.environ, {"ANTHROPIC_ADMIN_KEY": "fake-admin", "AI_STATUS_ACCOUNT_OPTIONS": '{"workspace_id":"work"}'}, clear=True), patch.object(query, "paginated", return_value=[]) as get:
            query.query()
        self.assertEqual(get.call_args.args[2]["group_by[]"], ["workspace_id"])
        self.assertNotIn("workspace_ids[]", get.call_args.args[2])


class OpenRouterTests(unittest.TestCase):
    def test_key_limit_uses_remaining_in_correct_period(self):
        parser = load("openrouter", "parse").parse
        metrics = parser(json.dumps({"data": {"usage": 200, "usage_monthly": 12, "limit": 100, "limit_remaining": 88, "limit_reset": "monthly"}}))["metrics"]
        self.assertEqual(metrics[0]["percentage"], 12)
        self.assertEqual(metrics[0]["type"], "monthly")
        self.assertEqual(metrics[0]["amount"], 12)
        self.assertEqual(metrics[0]["limit"], 100)
        self.assertEqual(metrics[0]["value_format"], "amount_ratio")
        self.assertIsNone(metrics[1]["percentage"])
        self.assertEqual(len({m["name"] for m in metrics}), 2)

    def test_account_spend_ratio_and_balance_use_account_scope(self):
        parser = load("openrouter", "parse").parse
        metrics = parser(json.dumps({"key": {"data": {"limit": None, "usage": 500, "usage_monthly": 12}},
                                      "credits": {"data": {"total_credits": 100, "total_usage": 25}}}))["metrics"]
        self.assertEqual([m["amount"] for m in metrics], [12, 25, 75])
        self.assertEqual([m["percentage"] for m in metrics], [None, 25, None])
        self.assertEqual(metrics[1]["limit"], 100)
        self.assertEqual(metrics[1]["value_format"], "amount_ratio")
        self.assertIn("Account spend", metrics[1]["detail"])
        self.assertEqual(len({render.metric_key(m) for m in metrics}), 3)

    def test_missing_or_invalid_credit_totals_never_invent_balance(self):
        parser = load("openrouter", "parse").parse
        for value in (None, True, "NaN", "Infinity", -1, [], {}):
            for field in ("total_credits", "total_usage"):
                with self.subTest(field=field, value=value):
                    credits = {"total_credits": 100, "total_usage": 25, field: value}
                    metrics = parser(json.dumps({"key": {"data": {"usage_monthly": 12}},
                                                 "credits": {"data": credits}}))["metrics"]
                    self.assertEqual([m["amount"] for m in metrics], [12])
        for credits in ({}, {"total_credits": 100}, {"total_usage": 25}):
            self.assertEqual(parser(json.dumps({"credits": {"data": credits}}))["metrics"], [])

    def test_zero_and_overdrawn_account_credit_balance(self):
        parser = load("openrouter", "parse").parse
        for total, spent, balance, percentage in ((0, 0, 0, None), (100, 120, -20, 120)):
            with self.subTest(total=total, spent=spent):
                metrics = parser(json.dumps({"credits": {"data": {"total_credits": total, "total_usage": spent}}}))["metrics"]
                self.assertEqual([m["amount"] for m in metrics], [spent, balance])
                self.assertEqual(metrics[0]["percentage"], percentage)
                self.assertIsNone(metrics[1]["percentage"])

    def test_extreme_credit_ratio_has_no_nonfinite_percentage(self):
        metrics = load("openrouter", "parse").parse(json.dumps({"credits": {"data": {"total_credits": 1e-300, "total_usage": 1e300}}}))["metrics"]
        self.assertIsNone(metrics[0]["percentage"])

    def test_api_budget_and_free_requests(self):
        parser = load("openrouter", "parse").parse
        metrics = parser(json.dumps({"data": {"effective_budget": {"limit_usd": 50, "spend_usd": 20, "reset_interval": "weekly", "resets_at": "2099-01-01T00:00:00Z"},
                                             "free_model_daily_requests": {"limit": 50, "used": 12}}}))["metrics"]
        self.assertEqual([m["percentage"] for m in metrics], [40, 24])
        self.assertIsNotNone(metrics[0]["reset_in_seconds"])

    def test_regular_key_never_calls_management_endpoint(self):
        query = load("openrouter", "query")
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-key"}, clear=True), patch.object(query, "json_request", return_value={"data": {"usage_monthly": 1}}) as get:
            result = query.query()
        get.assert_called_once()
        self.assertEqual(get.call_args.args[0], "https://openrouter.ai/api/v1/key")
        self.assertIn("OPENROUTER_MANAGEMENT_KEY", result["_ai_status"]["credits_hint"])
        metrics = load("openrouter", "parse").parse(json.dumps(result))["metrics"]
        self.assertEqual(metrics[0]["amount"], 1)
        self.assertIn("Set OPENROUTER_MANAGEMENT_KEY", metrics[0]["detail"])

    def test_requested_credits_without_management_keeps_key_usage(self):
        query = load("openrouter", "query")
        env = {"OPENROUTER_API_KEY": "fake-key", "AI_STATUS_ACCOUNT_OPTIONS": '{"include_credits":true}'}
        with patch.dict(os.environ, env, clear=True), patch.object(query, "json_request", return_value={"data": {"usage": 2}}) as get:
            result = query.query()
        get.assert_called_once()
        self.assertNotIn("credits", result)
        metrics = load("openrouter", "parse").parse(json.dumps(result))["metrics"]
        self.assertEqual(metrics[0]["amount"], 2)
        self.assertIn("OPENROUTER_MANAGEMENT_KEY", metrics[0]["detail"])

    def test_explicit_management_key_reads_account_credits(self):
        query = load("openrouter", "query")
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-key", "OPENROUTER_MANAGEMENT_KEY": "fake-management"}, clear=True), patch.object(query, "json_request", side_effect=[{"data": {}}, {"data": {"total_credits": 10, "total_usage": 2}}]) as get:
            result = query.query()
        self.assertEqual(get.call_args.args[1]["Authorization"], "Bearer fake-management")
        self.assertIn("credits", result)

    def test_management_key_alone_fetches_credits_directly(self):
        query = load("openrouter", "query")
        with patch.dict(os.environ, {"OPENROUTER_MANAGEMENT_KEY": "fake-management"}, clear=True), patch.object(query, "json_request", return_value={"data": {"total_credits": 10, "total_usage": 2}}) as get:
            result = query.query()
        get.assert_called_once_with("https://openrouter.ai/api/v1/credits", {"Authorization": "Bearer fake-management"})
        self.assertNotIn("key", result)
        self.assertEqual([m["amount"] for m in load("openrouter", "parse").parse(json.dumps(result))["metrics"]], [2, 8])

    def test_management_key_in_api_key_variable_is_detected(self):
        query = load("openrouter", "query")
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "fake-management"}, clear=True), patch.object(query, "json_request", side_effect=[{"data": {"is_management_key": True}}, {"data": {"total_credits": 10, "total_usage": 2}}]) as get:
            result = query.query()
        self.assertEqual(get.call_count, 2)
        self.assertEqual(get.call_args.args[1]["Authorization"], "Bearer fake-management")
        self.assertIn("credits", result)

    def test_credit_request_errors_keep_auth_and_rate_limit_metadata(self):
        query = load("openrouter", "query")
        env = {"OPENROUTER_API_KEY": "fake-key", "OPENROUTER_MANAGEMENT_KEY": "fake-management"}
        for status, retry in ((401, None), (403, None), (429, 123)):
            with self.subTest(status=status):
                error = provider_http.QueryError("Usage request failed.", status=status, retry_after_seconds=retry)
                with patch.dict(os.environ, env, clear=True), patch.object(query, "json_request", side_effect=[{"data": {"usage_monthly": 1}}, error]) as get, self.assertRaises(provider_http.QueryError) as caught:
                    query.query()
                self.assertIs(caught.exception, error)
                self.assertEqual(get.call_count, 2)

    def test_key_error_stops_before_credit_request(self):
        query = load("openrouter", "query")
        env = {"OPENROUTER_API_KEY": "fake-key", "OPENROUTER_MANAGEMENT_KEY": "fake-management"}
        error = provider_http.QueryError("Rate limited.", status=429, retry_after_seconds=60)
        with patch.dict(os.environ, env, clear=True), patch.object(query, "json_request", side_effect=error) as get, self.assertRaises(provider_http.QueryError) as caught:
            query.query()
        get.assert_called_once()
        self.assertIs(caught.exception, error)


class GoogleCloudTests(unittest.TestCase):
    def test_metric_identities_preserve_quota_location_and_window(self):
        parser = load("google-cloud", "parse").parse
        raw = {"allocation/usage": [series(4), series(3, location="europe-west1")],
               "limit": [series(10, limit_name="CPUs"), series(8, location="europe-west1", limit_name="CPUs")]}
        metrics = parser(json.dumps(raw))["metrics"]
        self.assertEqual(len({render.metric_key(m) for m in metrics}), 2)
        self.assertTrue(all(m["name"] == "Compute Engine · vCPUs" for m in metrics))
        self.assertEqual({m["detail"] for m in metrics}, {"p · us-central1", "p · europe-west1"})
        self.assertEqual(render.metric_key(metrics[0]),
                         "generic:p · compute.googleapis.com · compute.googleapis.com/cpus · us-central1")
        labels = {"limit_name": "Requests", "window_start_time": "2026-10-10T00:00:00Z"}
        raw = {"ratev2/net_usage": [series(10, **labels, window_size="1d"), series(2, **labels, window_size="1m")],
               "ratev2/limit": [series(100, limit_name="Requests", window_size="1d"), series(10, limit_name="Requests", window_size="1m")]}
        metrics = parser(json.dumps(raw))["metrics"]
        self.assertEqual(len({m["name"] for m in metrics}), 2)
        self.assertTrue(any("1d" in m["name"] for m in metrics))
        self.assertTrue(any("1m" in m["name"] for m in metrics))

    def test_quota_labels_omit_domains_and_keep_full_unknown_paths(self):
        parser = load("google-cloud", "parse").parse
        quotas = ["compute.googleapis.com/ssd_total_storage", "compute.googleapis.com/disks/read_ops",
                  "compute.googleapis.com/instances/read_ops"]
        raw = {"allocation/usage": [series(4, quota=quota) for quota in quotas],
               "limit": [series(10, quota=quota) for quota in quotas]}
        metrics = parser(json.dumps(raw))["metrics"]
        self.assertEqual(metrics[0]["name"], "Compute Engine · SSD storage")
        self.assertIn("Disks / Read ops", metrics[1]["name"])
        self.assertIn("Instances / Read ops", metrics[2]["name"])
        self.assertEqual(len({render.metric_key(m) for m in metrics}), 3)
        self.assertTrue(all(".googleapis.com" not in m["name"] + m["detail"] for m in metrics))
        self.assertTrue(all(m["percentage"] == 40 for m in metrics))

    def test_projects_and_services_retain_distinct_quota_identities(self):
        parser = load("google-cloud", "parse").parse
        usages = [series(2, quota="compute.googleapis.com/requests") for _ in range(3)]
        usages[1]["resource"]["labels"]["project_id"] = "other-project"
        usages[2]["resource"]["labels"]["service"] = "custom.googleapis.com"
        usages[2]["metric"]["labels"]["quota_metric"] = "custom.googleapis.com/requests"
        limits = json.loads(json.dumps(usages))
        for limit in limits:
            limit["points"][0]["value"]["int64Value"] = "10"
        metrics = parser(json.dumps({"allocation/usage": usages, "limit": limits}))["metrics"]
        self.assertEqual(len({render.metric_key(m) for m in metrics}), 3)
        self.assertIn("other-project", metrics[1]["detail"])
        self.assertEqual(metrics[2]["name"], "Custom · Requests")
        self.assertTrue(all(".googleapis.com" not in m["name"] + m["detail"] for m in metrics))

    def test_named_account_does_not_use_default_gcloud_credentials(self):
        query = load("google-cloud", "query")
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work"}, clear=True), patch.object(query, "run_cli") as run, self.assertRaises(provider_http.QueryError):
            query._token({})
        run.assert_not_called()

    def test_named_account_can_use_explicit_gcloud_profile(self):
        query = load("google-cloud", "query")
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work"}, clear=True), patch.object(query, "cli_path", return_value="gcloud"), patch.object(query, "run_cli", return_value="token") as run:
            self.assertEqual(query._token({"gcloud_account": "work@example.invalid"}), "token")
        self.assertIn("--account=work@example.invalid", run.call_args.args[0])

    def test_allocation_scope_matching_and_ambiguous_limits(self):
        parser = load("google-cloud", "parse").parse
        raw = {"allocation/usage": [series(4)], "limit": [series(10, limit_name="CPUs")], "ratev2/net_usage": [], "ratev2/limit": []}
        self.assertEqual(parser(json.dumps(raw))["metrics"][0]["percentage"], 40)
        raw["limit"] = [series(10, location="europe-west1", limit_name="CPUs")]
        self.assertIsNone(parser(json.dumps(raw))["metrics"][0]["percentage"])
        raw["limit"] = [series(10, limit_name="CPUs"), series(20, limit_name="another")]
        self.assertIsNone(parser(json.dumps(raw))["metrics"][0]["percentage"])

    def test_windowed_rate_sums_methods_only_in_same_latest_window(self):
        parser = load("google-cloud", "parse").parse
        labels = {"limit_name": "RequestsPerDay", "window_size": "1d"}
        raw = {"ratev2/net_usage": [series(20, **labels, method="A", window_start_time="2026-10-10T00:00:00Z"),
                                    series(10, **labels, method="B", window_start_time="2026-10-10T00:00:00Z"),
                                    series(80, **labels, method="A", window_start_time="2026-10-09T00:00:00Z")],
               "ratev2/limit": [series(100, **labels)]}
        metrics = parser(json.dumps(raw))["metrics"]
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0]["percentage"], 30)

    def test_billing_net_amount_and_empty_export_not_zero_balance(self):
        parser = load("google-cloud", "parse").parse
        result = parser(json.dumps({"billing_rows": [{"f": [{"v": "USD"}, {"v": "42.05"}]}]}))
        self.assertEqual(result["metrics"][0]["amount"], 42.05)
        self.assertIsNone(result["metrics"][0]["percentage"])
        self.assertEqual(parser('{"billing_rows":[]}')["metrics"], [])

    def test_monitoring_queries_latest_gauges_and_pagination(self):
        query = load("google-cloud", "query")
        now = datetime(2026, 10, 10, tzinfo=timezone.utc)
        pages = [{"timeSeries": [series(2)], "nextPageToken": "next"}, {"timeSeries": [series(3)]}]
        with patch.object(query, "json_request", side_effect=pages) as get:
            data = query._series("project", {}, "allocation/usage", now, now, {"service": "compute.googleapis.com"})
        self.assertEqual(len(data), 2)
        self.assertEqual(get.call_args.args[2]["pageToken"], "next")
        self.assertIn('resource.labels.service="compute.googleapis.com"', get.call_args.args[2]["filter"])

    def test_billing_parameterized_read_only_query_and_async_pagination(self):
        query = load("google-cloud", "query")
        start, now, _ = metered.month_window()
        job = {"projectId": "billing-project", "jobId": "job", "location": "EU"}
        row = {"f": [{"v": "USD"}, {"v": "1.5"}]}
        replies = [{"jobComplete": False, "jobReference": job}, {"jobComplete": True, "jobReference": job, "rows": [row], "pageToken": "more"},
                   {"jobComplete": True, "jobReference": job, "rows": [row]}]
        with patch.object(query, "json_request", side_effect=replies) as get:
            rows = query._billing("project", {}, {"billing_table": "bill.dataset.gcp_billing_export_v1_A", "billing_location": "EU"}, start, now)
        self.assertEqual(len(rows), 2)
        body = get.call_args_list[0].kwargs["data"]
        self.assertTrue(body["query"].startswith("SELECT "))
        self.assertIn("UNNEST(credits)", body["query"])
        self.assertIn("project.id = @project", body["query"])
        self.assertEqual(body["maximumBytesBilled"], "1000000000")
        self.assertEqual(get.call_args.args[2]["pageToken"], "more")
        self.assertEqual(get.call_args.args[2]["location"], "EU")

    def test_billing_rejects_sql_identifier_injection(self):
        query = load("google-cloud", "query")
        start, now, _ = metered.month_window()
        with patch.object(query, "json_request") as get, self.assertRaises(provider_http.QueryError):
            query._billing("p", {}, {"billing_table": "p.d.t` ; DROP TABLE t"}, start, now)
        get.assert_not_called()


class WindowsPostTests(unittest.TestCase):
    def test_native_send_request_uses_exact_binary_body(self):
        api = Mock()
        api.WinHttpOpen.return_value = 1
        api.WinHttpConnect.return_value = 2
        api.WinHttpOpenRequest.return_value = 3
        def query_headers(handle, flags, name, buffer, size, index):
            C.cast(buffer, C.POINTER(windows_http.DWORD))[0] = 200
            return True
        def read_data(handle, buffer, size, count):
            C.cast(count, C.POINTER(windows_http.DWORD))[0] = 0
            return True
        api.WinHttpQueryHeaders.side_effect = query_headers
        api.WinHttpReadData.side_effect = read_data
        body = b'{"read":"only"}'
        with patch.object(windows_http, "_api", return_value=api), patch.object(windows_http, "_proxy", return_value=(1, None, None)):
            self.assertEqual(windows_http._once("https://example.invalid", {}, 8, "POST", body), (200, b""))
        self.assertEqual(api.WinHttpOpenRequest.call_args.args[1], "POST")
        send = api.WinHttpSendRequest.call_args.args
        self.assertEqual(C.string_at(send[3], send[4]), body)
        self.assertEqual(send[4:6], (len(body), len(body)))

    def test_provider_http_forwards_post_on_windows(self):
        with patch("core.paths.IS_WINDOWS", True), patch.object(windows_http, "request", return_value=b'{}') as get:
            provider_http.request("https://example.invalid", method="POST", data=b'{"read":true}')
        self.assertEqual(get.call_args.kwargs, {"method": "POST", "data": b'{"read":true}'})

    def test_native_post_refuses_body_redirect_on_307(self):
        with patch.object(windows_http, "_once", side_effect=[(307, "/usage"), (200, b"ok")]) as once:
            with self.assertRaises(OSError):
                windows_http.request("https://example.invalid", method="POST", data=b"a=b")
        self.assertEqual(once.call_count, 1)


class RateLimitTests(unittest.TestCase):
    def test_native_retry_after_header_is_read_by_name(self):
        api = Mock()
        def query_headers(handle, flags, name, buffer, size, index):
            self.assertEqual(name, "Retry-After")
            C.cast(size, C.POINTER(windows_http.DWORD))[0] = 3 * C.sizeof(C.c_wchar)
            if buffer is not None:
                buffer.value = "75"
            return buffer is not None
        api.WinHttpQueryHeaders.side_effect = query_headers
        self.assertEqual(windows_http._retry_after(api, 3), "75")

    def test_retry_after_integer_date_missing_and_bounds(self):
        now = datetime(2026, 10, 10, 12, tzinfo=timezone.utc).timestamp()
        self.assertEqual(provider_http.retry_after_seconds("123", now), 123)
        self.assertEqual(provider_http.retry_after_seconds("Sat, 10 Oct 2026 12:02:00 GMT", now), 120)
        self.assertEqual(provider_http.retry_after_seconds(None, now), 300)
        self.assertEqual(provider_http.retry_after_seconds("invalid", now), 300)
        self.assertEqual(provider_http.retry_after_seconds("9999999", now), 86400)
        self.assertEqual(provider_http.retry_after_seconds("0", now), 1)
        self.assertEqual(provider_http.retry_after_seconds("Sat, 10 Oct 2026 11:00:00 GMT", now), 1)

    def test_windows_429_retry_header_survives_query_output(self):
        with patch("core.paths.IS_WINDOWS", True), patch.object(windows_http, "request", side_effect=windows_http.HTTPError(429, "75")):
            capture = io.StringIO()
            with redirect_stdout(capture):
                provider_http.output(lambda: provider_http.request("https://example.invalid", {"Authorization": "Bearer secret-key"}))
        result = json.loads(capture.getvalue())
        self.assertEqual(result["_ai_status_status"], 429)
        self.assertEqual(result["_ai_status_retry_after"], 75)
        self.assertNotIn("secret-key", result["_ai_status_error"])

    def test_linux_429_headers_survive_output(self):
        for header, expected in (("120", 120), (None, 300), ("Sat, 10 Oct 2026 12:02:00 GMT", 120)):
            error = urllib.error.HTTPError("https://example.invalid", 429, "secret", {"Retry-After": header} if header else {}, None)
            with patch("core.paths.IS_WINDOWS", False), patch("core.provider_http.urllib.request.build_opener") as opener, patch("core.provider_http.time.time", return_value=datetime(2026, 10, 10, 12, tzinfo=timezone.utc).timestamp()):
                opener.return_value.open.side_effect = error
                with self.assertRaises(provider_http.QueryError) as caught:
                    provider_http.request("https://example.invalid")
            self.assertEqual(caught.exception.status, 429)
            self.assertEqual(caught.exception.retry_after_seconds, expected)
            self.assertNotIn("secret", str(caught.exception))
            error.close()


class RedirectPolicyTests(unittest.TestCase):
    def test_live_local_get_redirect_and_cross_origin_credentials(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/same" or self.path == "/cross":
                    self.send_response(302)
                    self.send_header("Location", "/echo" if self.path == "/same" else self.server.other + "/echo")
                    self.end_headers()
                    return
                body = json.dumps(dict(self.headers)).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                self.send_response(307)
                self.send_header("Location", "/echo")
                self.end_headers()

            def log_message(self, *_):
                pass

        servers = [ThreadingHTTPServer(("127.0.0.1", 0), Handler) for _ in range(2)]
        threads = [threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True) for server in servers]
        for thread in threads:
            thread.start()
        first, second = [f"http://127.0.0.1:{server.server_port}" for server in servers]
        servers[0].other = second
        try:
            headers = {"Authorization": "Bearer secret", "Cookie": "secret-cookie", "x-api-key": "secret-key", "Accept": "application/json"}
            same = json.loads(provider_http.request(first + "/same", headers))
            self.assertEqual(same.get("Authorization"), "Bearer secret")
            cross = json.loads(provider_http.request(first + "/cross", headers))
            self.assertEqual(cross.get("Accept"), "application/json")
            self.assertFalse(any(name.lower() in {"authorization", "cookie", "x-api-key"} for name in cross))
            with self.assertRaises(provider_http.QueryError):
                provider_http.request(first + "/post", headers, method="POST", data=b"secret=value")
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for thread in threads:
                thread.join(timeout=1)

    def test_remote_http_and_https_downgrade_are_rejected(self):
        with self.assertRaises(provider_http.QueryError):
            provider_http.request("http://example.invalid")
        with self.assertRaises(ValueError):
            windows_http.request("http://example.invalid")
        request = __import__("urllib.request", fromlist=["Request"]).Request("https://example.invalid", headers={"Authorization": "secret"})
        with self.assertRaises(provider_http.QueryError):
            provider_http._UsageRedirects().redirect_request(request, None, 302, "redirect", {}, "http://localhost/path")

    def test_native_post_body_cannot_cross_origin(self):
        with patch.object(windows_http, "_once", return_value=(307, "https://other.invalid")), self.assertRaises(OSError):
            windows_http.request("https://example.invalid", method="POST", data=b"secret=value")

    def test_native_post_303_also_refused(self):
        with patch.object(windows_http, "_once", side_effect=[(303, "/result"), (200, b"ok")]) as once:
            with self.assertRaises(OSError):
                windows_http.request("https://example.invalid", method="POST", data=b"a=b")
        self.assertEqual(once.call_count, 1)


if __name__ == "__main__":
    unittest.main()
