"""Claude's macOS Keychain lookup stays read-only and isolated per account."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import accounts, fetch, macos_credentials
from core.provider_http import QueryError


class ClaudeKeychainTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="Claude config é ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.filename = self.root / ".credentials.json"
        self.file_credentials = {"accessToken": "file-token", "subscriptionType": "pro"}
        self.filename.write_text(json.dumps({"claudeAiOauth": self.file_credentials}))
        self.before = self.filename.read_bytes()
        environment = patch.dict(os.environ, {"USER": "mac-test", "HOME": str(self.root)}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)

    def reply(self, credentials=None, code=0, stdout=None, stderr=""):
        value = stdout if stdout is not None else json.dumps({"claudeAiOauth": credentials})
        return subprocess.CompletedProcess([], code, value, stderr)

    def test_live_keychain_credentials_outrank_stale_file_without_writing(self):
        credentials = {"accessToken": "keychain-token", "subscriptionType": "max"}
        with patch.object(macos_credentials.subprocess, "run", return_value=self.reply(credentials)) as run:
            self.assertEqual(macos_credentials.claude_credentials(self.root), credentials)
        self.assertEqual(run.call_args.args[0], ["/usr/bin/security", "find-generic-password", "-s",
                                                "Claude Code-credentials", "-w", "-a", "mac-test"])
        self.assertLessEqual(run.call_args.kwargs["timeout"], 10)
        self.assertEqual(self.filename.read_bytes(), self.before)

    def test_custom_directory_uses_scoped_service_and_never_unscoped_account(self):
        expected = "Claude Code-credentials-" + hashlib.sha256(str(self.root).encode()).hexdigest()[:8]
        with patch.object(macos_credentials.subprocess, "run", return_value=self.reply(code=44)) as run:
            self.assertEqual(macos_credentials.claude_credentials(self.root, scoped=True), self.file_credentials)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0][3], expected)
        self.assertEqual(self.filename.read_bytes(), self.before)

    def test_keychain_account_uses_connection_environment_without_mutating_parent(self):
        with patch.object(macos_credentials.subprocess, "run", return_value=self.reply(code=44)) as run:
            macos_credentials.claude_credentials(self.root, environ={"USER": "work-user"})
        self.assertEqual(run.call_args.args[0][-2:], ["-a", "work-user"])
        self.assertEqual(os.environ["USER"], "mac-test")

    def test_item_not_found_falls_back_to_credentials_file(self):
        with patch.object(macos_credentials.subprocess, "run", return_value=self.reply(code=44)):
            self.assertEqual(macos_credentials.claude_credentials(self.root), self.file_credentials)
        self.filename.unlink()
        with patch.object(macos_credentials.subprocess, "run", return_value=self.reply(code=44)):
            self.assertEqual(macos_credentials.claude_credentials(self.root), {})

    def test_expired_or_malformed_keychain_payload_falls_back_to_file(self):
        for reply in (self.reply({"accessToken": "expired-token", "expiresAt": 1}),
                      self.reply({"accessToken": "token", "expiresAt": "invalid"}),
                      self.reply({}), self.reply(stdout="not JSON"), self.reply(stdout="[]")):
            with self.subTest(payload=reply.stdout), patch.object(macos_credentials.subprocess, "run", return_value=reply):
                self.assertEqual(macos_credentials.claude_credentials(self.root), self.file_credentials)
        self.assertEqual(self.filename.read_bytes(), self.before)

    def test_denied_keychain_does_not_reuse_a_file_or_expose_raw_error(self):
        reply = self.reply(code=128, stdout="private-token", stderr="private-keychain-file")
        with patch.object(macos_credentials.subprocess, "run", return_value=reply), \
                patch.object(macos_credentials, "read_json") as read:
            with self.assertRaises(QueryError) as error:
                macos_credentials.claude_credentials(self.root)
        self.assertIn("Keychain", str(error.exception))
        self.assertNotIn("private-token", str(error.exception))
        self.assertNotIn("private-keychain-file", str(error.exception))
        read.assert_not_called()

    def test_timeout_and_missing_security_tool_report_safe_errors(self):
        for failure in (OSError("private-token"), subprocess.TimeoutExpired("security", 8, output="private-token")):
            with self.subTest(error=type(failure).__name__), patch.object(macos_credentials.subprocess, "run", side_effect=failure):
                with self.assertRaises(QueryError) as error:
                    macos_credentials.claude_credentials(self.root)
                self.assertIn("Keychain", str(error.exception))
                self.assertNotIn("private-token", str(error.exception))

    def load_query(self):
        filename = Path(__file__).resolve().parents[1] / "src/providers/claude/query.py"
        spec = importlib.util.spec_from_file_location("macos_claude_query_test", filename)
        query = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(query)
        return query

    def test_macos_collector_uses_scoped_keychain_token_and_plan(self):
        query = self.load_query()
        credentials = {"accessToken": "keychain-token", "subscriptionType": "max"}
        with patch.object(sys, "platform", "darwin"), \
                patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root)}), \
                patch.object(macos_credentials, "claude_credentials", return_value=credentials) as keychain, \
                patch.object(query, "request", return_value='{"five_hour":{"utilization":21}}') as request:
            result = query.query()
        keychain.assert_called_once_with(self.root, scoped=True)
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer keychain-token")
        self.assertEqual(result["plan"], "max")
        self.assertEqual(result["usage"]["five_hour"]["utilization"], 21)

    def test_non_macos_collector_uses_existing_file_without_keychain(self):
        query = self.load_query()
        with patch.object(sys, "platform", "linux"), \
                patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root)}), \
                patch.object(macos_credentials, "claude_credentials") as keychain, \
                patch.object(query, "request", return_value="{}") as request:
            result = query.query()
        keychain.assert_not_called()
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer file-token")
        self.assertEqual(result["plan"], "pro")

    def test_explicit_auth_file_is_authoritative_over_keychain_and_config_directory(self):
        query = self.load_query()
        auth_file = self.root / "work.json"
        auth_file.write_text(json.dumps({"claudeAiOauth": {"accessToken": "work-file-token"}}))
        with patch.object(sys, "platform", "darwin"), \
                patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work", "AI_STATUS_AUTH_FILE": str(auth_file),
                                        "CLAUDE_CONFIG_DIR": str(self.root)}), \
                patch.object(macos_credentials, "claude_credentials") as keychain, \
                patch.object(query.Path, "home", side_effect=AssertionError("implicit home accessed")), \
                patch.object(query, "request", return_value="{}") as request:
            query.query()
        keychain.assert_not_called()
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer work-file-token")

    def test_direct_token_uses_no_implicit_credentials_or_keychain(self):
        query = self.load_query()
        for account in ("", "work"):
            with self.subTest(account=account), patch.object(sys, "platform", "darwin"), \
                    patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": account, "CLAUDE_ACCESS_TOKEN": "direct-token"}), \
                    patch.object(macos_credentials, "claude_credentials") as keychain, \
                    patch.object(query.Path, "home", side_effect=AssertionError("implicit home accessed")), \
                    patch.object(query, "read_json") as read, \
                    patch.object(query, "request", return_value="{}") as request:
                result = query.query()
            keychain.assert_not_called()
            read.assert_not_called()
            self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer direct-token")
            self.assertEqual(result["plan"], "")

    def test_direct_token_is_not_replaced_by_expired_explicit_file(self):
        query = self.load_query()
        self.filename.write_text(json.dumps({"claudeAiOauth": {"accessToken": "expired-token", "expiresAt": 1}}))
        for account in ("", "work"):
            with self.subTest(account=account), patch.object(sys, "platform", "darwin"), \
                    patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": account, "CLAUDE_ACCESS_TOKEN": "direct-token",
                                            "AI_STATUS_AUTH_FILE": str(self.filename)}), \
                    patch.object(macos_credentials, "claude_credentials") as keychain, \
                    patch.object(query, "opencode_file", side_effect=AssertionError("another account accessed")), \
                    patch.object(query, "request", return_value="{}") as request:
                query.query()
            keychain.assert_not_called()
            self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer direct-token")

    def test_explicit_account_without_own_source_reads_no_implicit_login(self):
        query = self.load_query()
        with patch.object(sys, "platform", "darwin"), \
                patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work"}), \
                patch.object(macos_credentials, "claude_credentials") as keychain, \
                patch.object(query.Path, "home") as home, \
                patch.object(query, "read_json") as read, \
                patch.object(query, "request") as request:
            with self.assertRaises(QueryError) as error:
                query.query()
        self.assertIn("this Claude account", str(error.exception))
        keychain.assert_not_called()
        home.assert_not_called()
        read.assert_not_called()
        request.assert_not_called()

    def test_explicit_scoped_account_never_falls_back_to_opencode(self):
        query = self.load_query()
        for credentials in ({}, {"accessToken": "expired-token", "expiresAt": 1}):
            with self.subTest(credentials=credentials), patch.object(sys, "platform", "darwin"), \
                    patch.dict(os.environ, {"AI_STATUS_ACCOUNT_ID": "work", "CLAUDE_CONFIG_DIR": str(self.root)}), \
                    patch.object(macos_credentials, "claude_credentials", return_value=credentials) as keychain, \
                    patch.object(query, "read_json") as read, \
                    patch.object(query, "request") as request:
                with self.assertRaises(QueryError):
                    query.query()
            keychain.assert_called_once_with(self.root, scoped=True)
            read.assert_not_called()
            request.assert_not_called()

    def test_malformed_internal_snapshot_reports_safe_error_without_other_login(self):
        query = self.load_query()
        for snapshot in ("private-invalid-token", "[]"):
            with self.subTest(snapshot=snapshot), patch.object(sys, "platform", "darwin"), \
                    patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root), "AI_STATUS_CLAUDE_CREDENTIALS": snapshot}), \
                    patch.object(macos_credentials, "claude_credentials") as keychain, \
                    patch.object(query, "read_json") as read:
                with self.assertRaises(QueryError) as error:
                    query.query()
            self.assertNotIn("private-invalid-token", str(error.exception))
            keychain.assert_not_called()
            read.assert_not_called()


class ClaudeAccountFingerprintTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status Claude accounts ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.provider = self.root / "providers/claude"
        self.provider.mkdir(parents=True)
        (self.provider / "query.py").write_text("# collector stub\n")
        self.environment = {"HOME": str(self.root), "USER": "mac-test", "WORK_DIR": str(self.root / "work")}
        self.default = {"provider": "claude", "connection_id": "claude", "account_id": None, "env": {}, "options": {}}
        self.scoped = accounts.connection(accounts.normalize({
            "id": "work", "provider": "claude", "env": {"CLAUDE_CONFIG_DIR": "WORK_DIR"}}))
        for target, key, value in ((fetch, "CACHE_DIR", str(self.root / "cache")), (fetch, "MIN_SERVICE_INTERVAL", 0)):
            patched = patch.object(target, key, value)
            patched.start()
            self.addCleanup(patched.stop)
        environment = patch.dict(os.environ, self.environment, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        platform = patch.object(sys, "platform", "darwin")
        platform.start()
        self.addCleanup(platform.stop)

    def credentials(self, name="first"):
        return {"accessToken": name + "-access-token", "refreshToken": name + "-refresh-token", "subscriptionType": "max"}

    def test_default_and_scoped_fingerprints_track_live_keychain_rotation_and_redaction(self):
        for connection in (self.default, self.scoped):
            with self.subTest(connection=connection["connection_id"]), \
                    patch.object(macos_credentials, "claude_credentials", side_effect=[self.credentials(), self.credentials("second")]) as keychain:
                first_env, first_digest, first_secrets = accounts.prepare(connection, self.environment)
                second_env, second_digest, second_secrets = accounts.prepare(connection, self.environment)
            self.assertNotEqual(first_digest, second_digest)
            self.assertEqual(json.loads(first_env["AI_STATUS_CLAUDE_CREDENTIALS"]), self.credentials())
            self.assertEqual(json.loads(second_env["AI_STATUS_CLAUDE_CREDENTIALS"]), self.credentials("second"))
            self.assertIn("first-access-token", first_secrets)
            self.assertIn("first-refresh-token", first_secrets)
            self.assertIn("second-access-token", second_secrets)
            self.assertEqual(accounts.redact("first-access-token first-refresh-token", first_secrets), "[redacted] [redacted]")
            expected_root = self.root / ("work" if connection.get("account_id") else ".claude")
            self.assertEqual(keychain.call_args.args, (expected_root,))
            self.assertEqual(keychain.call_args.kwargs["scoped"], bool(connection.get("account_id")))
            self.assertEqual(keychain.call_args.kwargs["environ"]["USER"], "mac-test")
        self.assertNotIn("AI_STATUS_CLAUDE_CREDENTIALS", os.environ)

    def test_snapshot_is_used_by_query_without_second_keychain_read(self):
        query = ClaudeKeychainTests.load_query(self)
        with patch.object(macos_credentials, "claude_credentials", side_effect=[self.credentials(), self.credentials("rotated")]) as keychain:
            prepared_env, digest, secrets = accounts.prepare(self.scoped, self.environment)
            with patch.dict(os.environ, prepared_env, clear=True), \
                    patch.object(query.Path, "home", side_effect=AssertionError("implicit home accessed")), \
                    patch.object(query, "read_json") as read, \
                    patch.object(query, "request", return_value="{}") as request:
                result = query.query()
        self.assertEqual(keychain.call_count, 1)
        read.assert_not_called()
        self.assertEqual(request.call_args.args[1]["Authorization"], "Bearer first-access-token")
        self.assertEqual(result["plan"], "max")
        self.assertNotIn("first-access-token", digest)
        self.assertIn("first-refresh-token", secrets)

    def test_inherited_snapshot_is_discarded_and_resolved_for_current_connection(self):
        environment = {**self.environment, "AI_STATUS_CLAUDE_CREDENTIALS": json.dumps(self.credentials("other-account")),
                       "AI_STATUS_ACCOUNT_ID": "other-account", "AI_STATUS_AUTH_FILE": "/other/account.json"}
        with patch.object(macos_credentials, "claude_credentials", return_value=self.credentials()):
            prepared, _, secrets = accounts.prepare(self.scoped, environment)
        self.assertEqual(prepared["AI_STATUS_ACCOUNT_ID"], "work")
        self.assertNotIn("AI_STATUS_AUTH_FILE", prepared)
        self.assertEqual(json.loads(prepared["AI_STATUS_CLAUDE_CREDENTIALS"]), self.credentials())
        self.assertNotIn("other-account-access-token", secrets)

    def test_explicit_auth_file_and_direct_token_never_read_keychain(self):
        auth_file = self.root / "work.json"
        auth_file.write_text(json.dumps({"claudeAiOauth": self.credentials("file")}))
        file_connection = accounts.connection(accounts.normalize({"id": "file", "provider": "claude", "auth_file": str(auth_file)}))
        direct_connection = accounts.connection(accounts.normalize({"id": "direct", "provider": "claude", "env": {"CLAUDE_ACCESS_TOKEN": "WORK_TOKEN"}}))
        environment = {**self.environment, "WORK_TOKEN": "direct-token", "AI_STATUS_CLAUDE_CREDENTIALS": "inherited-secret"}
        for connection in (file_connection, direct_connection):
            with self.subTest(connection=connection["connection_id"]), patch.object(macos_credentials, "claude_credentials") as keychain:
                prepared, _, _ = accounts.prepare(connection, environment)
            keychain.assert_not_called()
            self.assertNotIn("AI_STATUS_CLAUDE_CREDENTIALS", prepared)

    def test_explicit_account_without_source_does_not_inspect_default_keychain(self):
        connection = accounts.connection(accounts.normalize({"id": "missing", "provider": "claude"}))
        environment = {**self.environment, "CLAUDE_CONFIG_DIR": str(self.root / "another-account"),
                       "CLAUDE_ACCESS_TOKEN": "another-account-token", "AI_STATUS_CLAUDE_CREDENTIALS": "another-account"}
        with patch.object(macos_credentials, "claude_credentials") as keychain:
            prepared, _, _ = accounts.prepare(connection, environment)
        keychain.assert_not_called()
        self.assertNotIn("CLAUDE_CONFIG_DIR", prepared)
        self.assertNotIn("CLAUDE_ACCESS_TOKEN", prepared)
        self.assertNotIn("AI_STATUS_CLAUDE_CREDENTIALS", prepared)

    def test_non_macos_preparation_avoids_keychain_and_internal_snapshot(self):
        with patch.object(sys, "platform", "linux"), patch.object(macos_credentials, "claude_credentials") as keychain:
            prepared, _, _ = accounts.prepare(self.scoped, self.environment)
        keychain.assert_not_called()
        self.assertNotIn("AI_STATUS_CLAUDE_CREDENTIALS", prepared)

    def test_keychain_denial_bypasses_previous_usage_cache_and_collector(self):
        previous = {"provider": "Previous account", "metrics": [{"percentage": 88}]}
        with patch.object(macos_credentials, "claude_credentials", return_value=self.credentials()):
            fingerprint = accounts.prepare(self.default)[1]
        fetch._save_cache(str(self.provider), previous, self.default, fingerprint)
        denied = subprocess.CompletedProcess([], 128, "private-token", "private-keychain-path")
        with patch.object(macos_credentials.subprocess, "run", return_value=denied) as run, \
                patch.object(fetch, "_load_cache", wraps=fetch._load_cache) as load:
            result = fetch.run_provider(str(self.provider), self.default)
        self.assertIn("Keychain", result["error"])
        self.assertNotIn("private-token", json.dumps(result))
        self.assertNotIn("private-keychain-path", json.dumps(result))
        self.assertNotIn("_cached", result)
        load.assert_not_called()
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][0], "/usr/bin/security")

    def test_rotated_keychain_login_never_reuses_previous_accounts_fresh_cache(self):
        previous = {"provider": "Previous account", "metrics": [{"percentage": 88}]}
        with patch.object(macos_credentials, "claude_credentials", return_value=self.credentials()):
            fingerprint = accounts.prepare(self.default)[1]
        fetch._save_cache(str(self.provider), previous, self.default, fingerprint)
        failed = subprocess.CompletedProcess([], 1, "", "")
        with patch.object(macos_credentials, "claude_credentials", return_value=self.credentials("rotated")), \
                patch.object(fetch.subprocess, "run", return_value=failed) as run, \
                patch.object(fetch, "_pace_service"):
            result = fetch.run_provider(str(self.provider), self.default)
        self.assertIn("error", result)
        self.assertNotIn("_cached", result)
        self.assertNotIn("Previous account", json.dumps(result))
        run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
