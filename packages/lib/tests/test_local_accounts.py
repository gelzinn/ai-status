import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from core import accounts, paths
from core.provider_http import QueryError


def provider(name, kind="query"):
    spec = importlib.util.spec_from_file_location(name + "_account_" + kind, SRC / "providers" / name / (kind + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LocalAccountTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status local accounts ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work", "AI_STATUS_ACCOUNT_OPTIONS": "{}",
                                               "HOME": str(self.root)}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def test_kiro_json_account_queries_its_profile_without_cli(self):
        credentials = self.root / "kiro.json"
        paths.atomic_json(credentials, {"access_token": "work-kiro-token", "region": "eu-west-1",
                                        "profile_arn": "arn:aws:codewhisperer:eu-west-1:123:profile/work", "expires_at": "2100-01-01T00:00:00Z"})
        module = provider("kiro")
        with patch.dict(os.environ, {"AI_STATUS_AUTH_FILE": str(credentials)}), patch.object(module, "json_request", return_value={"usageBreakdownList": []}) as request, patch.object(module, "run_cli") as cli:
            module.query()
        cli.assert_not_called()
        self.assertEqual(request.call_args.args[0], "https://codewhisperer.eu-west-1.amazonaws.com/")
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer work-kiro-token")
        self.assertEqual(request.call_args.kwargs["method"], "POST")
        self.assertEqual(request.call_args.kwargs["data"], {"origin": "AI_EDITOR", "profileArn": "arn:aws:codewhisperer:eu-west-1:123:profile/work", "resourceType": "AGENTIC_REQUEST"})

    def test_kiro_sqlite_account_is_read_only_and_fingerprints_live_wal(self):
        database = self.root / "data.sqlite3"
        with sqlite3.connect(database) as connection:
            connection.execute("CREATE TABLE auth_kv (key TEXT, value TEXT)")
            connection.execute("CREATE TABLE state (key TEXT, value TEXT)")
            connection.execute("INSERT INTO auth_kv VALUES (?, ?)", ("kirocli:odic:token", json.dumps({"access_token": "saved-kiro-token", "region": "us-east-1"})))
            connection.execute("INSERT INTO state VALUES (?, ?)", ("api.codewhisperer.profile", '{"arn":"selected-profile"}'))
        before = database.read_bytes()
        module = provider("kiro")
        with patch.dict(os.environ, {"AI_STATUS_AUTH_FILE": str(database)}), patch.object(module, "json_request", return_value={}) as request:
            module.query()
        self.assertEqual(database.read_bytes(), before)
        self.assertEqual(request.call_args.kwargs["data"]["profileArn"], "selected-profile")
        writer = sqlite3.connect(database)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        record = accounts.connection(accounts.normalize({"id": "work", "provider": "kiro", "auth_file": str(database)}))
        env, digest, secrets = accounts.prepare(record)
        self.assertIn("saved-kiro-token", secrets)
        writer.execute("INSERT INTO state VALUES (?, ?)", ("chat.unrelated", "new-activity"))
        writer.commit()
        self.assertTrue(Path(str(database) + "-wal").is_file())
        self.assertEqual(accounts.prepare(record)[1], digest)
        writer.execute("UPDATE auth_kv SET value=? WHERE key=?", (json.dumps({"access_token": "rotated-kiro-token", "region": "us-east-1"}), "kirocli:odic:token"))
        writer.commit()
        env, rotated, secrets = accounts.prepare(record)
        self.assertNotEqual(rotated, digest)
        self.assertIn("rotated-kiro-token", secrets)

    def test_kiro_empty_expired_or_invalid_region_never_uses_global_cli(self):
        module = provider("kiro")
        with patch.object(module, "json_request") as request, patch.object(module, "run_cli") as cli:
            with self.assertRaises(QueryError):
                module.query()
            with patch.dict(os.environ, {"KIRO_ACCESS_TOKEN": "work-token", "AI_STATUS_ACCOUNT_OPTIONS": '{"region":"us-east-1.evil.example"}'}):
                with self.assertRaises(QueryError):
                    module.query()
            credentials = self.root / "expired.json"
            paths.atomic_json(credentials, {"access_token": "must-not-leak", "region": "us-east-1", "expires_at": "2000-01-01T00:00:00Z"})
            with patch.dict(os.environ, {"AI_STATUS_AUTH_FILE": str(credentials)}):
                with self.assertRaises(QueryError) as error:
                    module.query()
                self.assertNotIn("must-not-leak", str(error.exception))
        request.assert_not_called()
        cli.assert_not_called()

    def test_kiro_json_parser_selects_credit_pool_and_preserves_amount_and_reset(self):
        parser = provider("kiro", "parse")
        data = {"subscriptionInfo": {"subscriptionTitle": "KIRO PRO"}, "nextDateReset": 4102444800,
                "usageBreakdownList": [{"resourceType": "OTHER", "currentUsageWithPrecision": 99, "usageLimitWithPrecision": 100},
                                       {"resourceType": "CREDIT", "currentUsageWithPrecision": 42.5, "usageLimitWithPrecision": 500}]}
        result = parser.parse(json.dumps(data))
        self.assertEqual(result["plan"], "KIRO PRO")
        self.assertEqual(result["metrics"][0]["percentage"], 8.5)
        self.assertEqual(result["metrics"][0]["amount"], 42.5)
        self.assertGreater(result["metrics"][0]["reset_in_seconds"], 0)
        data["usageBreakdownList"][1]["currentUsageWithPrecision"] = None
        self.assertEqual(parser.parse(json.dumps(data))["metrics"], [])
        self.assertEqual(parser.parse("KIRO PRO\nCredits (40 of 100)\n")["metrics"][0]["percentage"], 40)

    def test_antigravity_explicit_oauth_file_and_token_use_fixed_quota_endpoint(self):
        credentials = self.root / "antigravity.json"
        paths.atomic_json(credentials, {"token": {"access_token": "work-antigravity-token", "expiry": "2100-01-01T00:00:00Z"}})
        module = provider("antigravity")
        with patch.dict(os.environ, {"AI_STATUS_AUTH_FILE": str(credentials)}), patch.object(module, "json_request", return_value={}) as request:
            module.query()
        self.assertEqual(request.call_args.args[0], "https://daily-cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary")
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer work-antigravity-token")
        self.assertEqual(request.call_args.kwargs["data"], {})
        with patch.dict(os.environ, {"ANTIGRAVITY_ACCESS_TOKEN": "override-token"}), patch.object(module, "json_request", return_value={}) as request:
            module.query()
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer override-token")

    def test_antigravity_account_does_not_read_default_credentials(self):
        default = self.root / ".gemini/antigravity-cli/antigravity-oauth-token"
        paths.atomic_json(default, {"access_token": "primary-token"})
        module = provider("antigravity")
        with patch.object(module, "json_request") as request, self.assertRaises(QueryError) as error:
            module.query()
        request.assert_not_called()
        self.assertNotIn("primary-token", str(error.exception))

    def test_antigravity_api_parser_preserves_each_pool_and_window(self):
        parser = provider("antigravity", "parse")
        raw = {"response": {"groups": [
            {"displayName": "Gemini Models", "buckets": [
                {"bucketId": "gemini-weekly", "remainingFraction": 0.9, "resetTime": "2100-01-01T00:00:00Z"},
                {"bucketId": "gemini-5h", "remainingFraction": 0.4, "resetTime": "2100-01-02T00:00:00Z"}]},
            {"displayName": "Claude and GPT Models", "buckets": [{"bucketId": "3p-weekly", "remainingFraction": 0.2}]}]}}
        result = parser.parse(json.dumps(raw))
        self.assertEqual(len(result), 2)
        self.assertEqual([metric["percentage"] for metric in result[0]["metrics"]], [10, 60])
        self.assertEqual(result[1]["metrics"][0]["percentage"], 80)
        self.assertNotEqual(result[0]["metrics"][0]["reset_in_seconds"], result[0]["metrics"][1]["reset_in_seconds"])
        raw["response"]["groups"][0]["buckets"][0]["remainingFraction"] = 2
        self.assertEqual(parser.parse(json.dumps(raw))[0]["metrics"], [])

    def test_antigravity_unsupported_cadence_and_duplicate_window_not_guessed(self):
        parser = provider("antigravity", "parse")
        raw = {"groups": [{"displayName": "Gemini", "buckets": [
            {"bucketId": "gemini-monthly", "window": "monthly", "remainingFraction": 0.1},
            {"bucketId": "gemini-weekly", "window": "weekly", "remainingFraction": 0.9}]}]}
        self.assertEqual([metric["type"] for metric in parser.parse(json.dumps(raw))[0]["metrics"]], ["weekly"])
        raw["groups"][0]["buckets"].append({"bucketId": "another-weekly", "window": "weekly", "remainingFraction": 0.2})
        self.assertEqual(parser.parse(json.dumps(raw))[0]["metrics"], [])


if __name__ == "__main__":
    unittest.main()
