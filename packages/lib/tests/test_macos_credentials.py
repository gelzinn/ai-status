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
from core import macos_credentials
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
        environment = patch.dict(os.environ, {"USER": "mac-test"})
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


if __name__ == "__main__":
    unittest.main()
