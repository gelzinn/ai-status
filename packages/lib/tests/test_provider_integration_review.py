"""Integration boundaries: account isolation and independently selectable metrics."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from core import accounts, render
from core.provider_http import QueryError

PROVIDERS = Path(__file__).resolve().parents[1] / "src/providers"


def load(provider, module):
    spec = importlib.util.spec_from_file_location("review_" + provider.replace("-", "_") + module,
                                                  PROVIDERS / provider / (module + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ProviderIntegrationReview(unittest.TestCase):
    def test_commandcode_missing_values_never_become_zero_amounts(self):
        parser = load("commandcode", "parse").parse
        for payload in ({}, {"error": "secret"}, {"errors": []}, {"used": "NaN", "remaining": None}):
            parsed = parser(json.dumps(payload))
            self.assertEqual(parsed["metrics"], [])
            self.assertIn("_error", parsed)
        for payload, expected in (({"used": 0}, [("monthly", 0)]), ({"remaining": -2}, [("balance", -2)]),
                                  ({"windows": {"weekly": {"used": 2, "cap": 10}}}, [("weekly", 2)])):
            parsed = parser(json.dumps(payload))
            self.assertEqual([(metric["type"], metric["amount"]) for metric in parsed["metrics"]], expected)

    def test_commandcode_query_omits_missing_spend_and_rejects_empty_or_error_reports(self):
        query = load("commandcode", "query")
        with patch.dict(os.environ, {"COMMANDCODE_API_KEY": "second-key"}, clear=True):
            with patch.object(query, "request", return_value='{"error":"secret"}'):
                with self.assertRaises(QueryError) as error:
                    query._get("/alpha/billing/credits", "second-key")
                self.assertNotIn("secret", str(error.exception))
            with patch.object(query, "_get", side_effect=[{}, {}, {}, {}]):
                with self.assertRaises(QueryError):
                    query.query()
            with patch.object(query, "_get", side_effect=[{}, {}, {"credits": {"monthlyCredits": 0}}, {}]):
                result = query.query()
            self.assertIsNone(result["used"])
            self.assertEqual(result["remaining"], 0)
            parsed = load("commandcode", "parse").parse(json.dumps(result))
            self.assertEqual([(metric["type"], metric["amount"]) for metric in parsed["metrics"]], [("balance", 0)])

    def test_codex_direct_account_token_omits_default_file_account_header(self):
        query = load("codex", "query")
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "second", "CODEX_ACCESS_TOKEN": "second-token"}, clear=True), \
                patch.object(query, "read_json", return_value={"tokens": {"account_id": "primary-id"}}) as read, \
                patch.object(query, "request", return_value='{"rate_limit":{}}') as request:
            query.query()
        read.assert_not_called()
        self.assertEqual(request.call_args.args[1], {"Authorization": "Bearer second-token"})

    def test_claude_direct_account_token_omits_default_file_subscription(self):
        query = load("claude", "query")
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "second", "CLAUDE_ACCESS_TOKEN": "second-token"}, clear=True), \
                patch.object(query, "read_json", return_value={"claudeAiOauth": {"subscriptionType": "primary-plan", "expiresAt": 1}}) as read, \
                patch.object(query, "request", return_value='{"five_hour":{"utilization":0}}') as request:
            result = query.query()
        read.assert_not_called()
        self.assertEqual(result["plan"], "")
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer second-token")
        self.assertEqual(request.call_args.args[0], "https://api.anthropic.com/api/oauth/usage?cedar_ember=1")
        self.assertEqual(request.call_args.args[1]["User-Agent"], "claude-cli/2.1.281 (external, cli)")

    def test_saved_anthropic_key_does_not_inherit_default_admin_oauth(self):
        record = accounts.connection(accounts.normalize({"id": "second", "provider": "anthropic-api",
                                    "env": {"ANTHROPIC_ADMIN_KEY": "SECOND_ADMIN_KEY"}}))
        env, _, _ = accounts.prepare(record, {"ANTHROPIC_ADMIN_TOKEN": "primary-oauth",
                                              "SECOND_ADMIN_KEY": "second-key"})
        query = load("anthropic-api", "query")
        with patch.dict(os.environ, env, clear=True), patch.object(query, "paginated", return_value=[]) as get:
            query.query()
        headers = get.call_args.args[1]
        self.assertEqual(headers.get("x-api-key"), "second-key")
        self.assertNotIn("Authorization", headers)

    def test_saved_google_account_without_credentials_does_not_use_global_gcloud(self):
        query = load("google-cloud", "query")
        with patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "second"}, clear=True), \
                patch.object(query, "run_cli", return_value="primary-token") as cli:
            with self.assertRaises(QueryError):
                query._token({})
            cli.assert_not_called()

    def assert_selectable(self, metrics):
        keys = [render.metric_key(metric) for metric in metrics]
        self.assertGreater(len(metrics), 1)
        self.assertEqual(len(keys), len(set(keys)), keys)

    def test_openrouter_key_limit_and_month_spend_are_separately_selectable(self):
        parsed = load("openrouter", "parse").parse(json.dumps({"data": {
            "limit": 100, "limit_remaining": 88, "limit_reset": "monthly", "usage_monthly": 12}}))
        self.assert_selectable(parsed["metrics"])

    def test_costs_in_different_currencies_are_separately_selectable(self):
        parsed = load("openai-api", "parse").parse(json.dumps({"data": [{"results": [
            {"amount": {"value": 2, "currency": "usd"}},
            {"amount": {"value": 3, "currency": "eur"}}]}]}))
        self.assert_selectable(parsed["metrics"])

    def test_google_same_quota_in_different_locations_is_separately_selectable(self):
        def series(location, value):
            return {"resource": {"type": "consumer_quota", "labels": {"project_id": "p", "location": location}},
                    "metric": {"labels": {"quota_metric": "compute.googleapis.com/cpus"}},
                    "points": [{"interval": {"endTime": "2026-10-10T10:00:00Z"},
                                "value": {"int64Value": str(value)}}]}
        parsed = load("google-cloud", "parse").parse(json.dumps({
            "allocation/usage": [series("us-central1", 2), series("europe-west1", 3)],
            "limit": [series("us-central1", 10), series("europe-west1", 20)]}))
        self.assert_selectable(parsed["metrics"])


if __name__ == "__main__":
    unittest.main()
