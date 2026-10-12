"""Stable alert identity follows the credential source used for collection."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import accounts, notifications


class NotificationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = {"HOME": str(self.root)}

    def write(self, filename, document):
        filename = self.root / filename
        filename.parent.mkdir(parents=True, exist_ok=True)
        filename.write_text(json.dumps(document), encoding="utf-8")
        return str(filename)

    def identity(self, provider, env=None, fingerprint="cache-context-1", explicit=False):
        connection = {"provider": provider, "connection_id": "account:personal" if explicit else provider,
                      "account_id": "personal" if explicit else None}
        return accounts.notification_identity(connection, self.env if env is None else env, fingerprint)

    def test_codex_account_token_refresh_preserves_identity_and_switch_changes_it(self):
        self.write(".codex/auth.json", {"tokens": {"access_token": "old-token", "account_id": "account-one"}})
        first = self.identity("codex")
        self.write(".codex/auth.json", {"tokens": {"access_token": "refreshed-token", "account_id": "account-one"}})
        self.assertEqual(first, self.identity("codex", fingerprint="cache-context-2"))
        self.write(".codex/auth.json", {"tokens": {"access_token": "different-token", "account_id": "account-two"}})
        self.assertNotEqual(first, self.identity("codex"))
        self.assertRegex(first, r"^[a-f0-9]{64}$")

    def test_codex_direct_token_does_not_use_unselected_native_file(self):
        self.write(".codex/auth.json", {"tokens": {"access_token": "native-token", "account_id": "native-account"}})
        env = dict(self.env, CODEX_ACCESS_TOKEN="direct-token")
        first = self.identity("codex", env)
        self.write(".codex/auth.json", {"tokens": {"access_token": "other-native-token", "account_id": "other-native-account"}})
        self.assertEqual(first, self.identity("codex", env, fingerprint="changed-unrelated-file"))
        self.assertNotEqual(first, self.identity("codex", dict(env, CODEX_ACCESS_TOKEN="different-direct-token")))
        self.assertEqual(self.identity("codex", dict(env, CODEX_ACCOUNT_ID="selected-account")),
                         self.identity("codex", dict(env, CODEX_ACCESS_TOKEN="rotated", CODEX_ACCOUNT_ID="selected-account")))

    def test_codex_jwt_subject_and_account_stay_stable_during_refresh(self):
        def jwt(subject, account, expires):
            claims = json.dumps({"sub": subject, "exp": expires,
                                 "https://api.openai.com/auth": {"chatgpt_account_id": account}}).encode()
            payload = base64.urlsafe_b64encode(claims).decode().rstrip("=")
            return "header." + payload + ".signature"
        first = self.identity("codex", dict(self.env, CODEX_ACCESS_TOKEN=jwt("user-one", "account-one", 100)))
        self.assertEqual(first, self.identity("codex", dict(self.env, CODEX_ACCESS_TOKEN=jwt("user-one", "account-one", 200))))
        self.assertNotEqual(first, self.identity("codex", dict(self.env, CODEX_ACCESS_TOKEN=jwt("user-two", "account-one", 200))))
        self.assertNotEqual(first, self.identity("codex", dict(self.env, CODEX_ACCESS_TOKEN=jwt("user-one", "account-two", 200))))
        self.assertRegex(first, r"^[a-f0-9]{64}$")

    def test_codex_explicit_file_does_not_use_native_account(self):
        self.write(".codex/auth.json", {"tokens": {"access_token": "native-token", "account_id": "native-account"}})
        filename = self.write("custom/codex.json", {"tokens": {"access_token": "selected-token", "account_id": "selected-account"}})
        env = dict(self.env, AI_STATUS_AUTH_FILE=filename)
        first = self.identity("codex", env, explicit=True)
        self.write(".codex/auth.json", {"tokens": {"access_token": "new-native-token", "account_id": "new-native-account"}})
        self.assertEqual(first, self.identity("codex", env, explicit=True))

    def test_claude_native_account_metadata_survives_token_refresh(self):
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "old-token", "expiresAt": 0}})
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "account-one", "organizationUuid": "org-one"}})
        first = self.identity("claude")
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "refreshed-token", "expiresAt": 0}})
        self.assertEqual(first, self.identity("claude", fingerprint="changed-context"))
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "account-two", "organizationUuid": "org-one"}})
        self.assertNotEqual(first, self.identity("claude"))

    def test_claude_explicit_file_ignores_unrelated_home_metadata(self):
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "unrelated-account", "organizationUuid": "unrelated-org"}})
        filename = self.write("custom/credentials.json", {"claudeAiOauth": {"accessToken": "selected-token"}})
        env = dict(self.env, AI_STATUS_AUTH_FILE=filename)
        first = self.identity("claude", env, explicit=True)
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "changed-unrelated-account"}})
        self.assertEqual(first, self.identity("claude", env, explicit=True))
        self.write("custom/credentials.json", {"claudeAiOauth": {"accessToken": "different-selected-token"}})
        self.assertNotEqual(first, self.identity("claude", env, explicit=True))
        self.write("custom/.claude.json", {"oauthAccount": {"accountUuid": "selected-account", "organizationUuid": "org-one"}})
        stable = self.identity("claude", env, explicit=True)
        self.write("custom/credentials.json", {"claudeAiOauth": {"accessToken": "rotated-selected-token"}})
        self.assertEqual(stable, self.identity("claude", env, explicit=True))

    def test_claude_custom_root_uses_only_its_account_metadata(self):
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "native-account"}})
        self.write("scoped/.credentials.json", {"claudeAiOauth": {"accessToken": "scoped-token"}})
        self.write("scoped/.claude.json", {"oauthAccount": {"accountUuid": "scoped-account"}})
        env = dict(self.env, CLAUDE_CONFIG_DIR=str(self.root / "scoped"))
        first = self.identity("claude", env, explicit=True)
        self.write("scoped/.credentials.json", {"claudeAiOauth": {"accessToken": "rotated-scoped-token"}})
        self.assertEqual(first, self.identity("claude", env, explicit=True))
        self.write("scoped/.claude.json", {"oauthAccount": {"accountUuid": "different-scoped-account"}})
        self.assertNotEqual(first, self.identity("claude", env, explicit=True))

    def test_claude_direct_token_ignores_unrelated_native_metadata(self):
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "native-token"}})
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "native-account"}})
        env = dict(self.env, CLAUDE_ACCESS_TOKEN="direct-token")
        first = self.identity("claude", env)
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "other-native-account"}})
        self.assertEqual(first, self.identity("claude", env, fingerprint="unrelated-context-change"))
        self.assertNotEqual(first, self.identity("claude", dict(env, CLAUDE_ACCESS_TOKEN="other-direct-token")))

    def test_claude_expired_native_login_uses_selected_opencode_session(self):
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "expired-native", "expiresAt": 1}})
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "native-account"}})
        self.write(".local/share/opencode/auth.json", {"anthropic": {"access": "active-opencode-token"}})
        first = self.identity("claude")
        self.write(".claude.json", {"oauthAccount": {"accountUuid": "other-native-account"}})
        self.assertEqual(first, self.identity("claude", fingerprint="unrelated-context-change"))
        self.write(".local/share/opencode/auth.json", {"anthropic": {"access": "different-opencode-token"}})
        self.assertNotEqual(first, self.identity("claude"))

    def test_claude_actual_token_fallback_ignores_unrelated_opencode_rotation(self):
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "actual-native-token"}})
        first = self.identity("claude")
        self.write(".local/share/opencode/auth.json", {"other-provider": {"access": "unrelated-token"}})
        self.assertEqual(first, self.identity("claude", fingerprint="new-prepare-fingerprint"))

    def test_prepared_macos_snapshot_uses_selected_token(self):
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "stale-file-token"}})
        env = dict(self.env, AI_STATUS_CLAUDE_CREDENTIALS=json.dumps({"accessToken": "keychain-token"}))
        first = self.identity("claude", env)
        self.write(".claude/.credentials.json", {"claudeAiOauth": {"accessToken": "changed-stale-file-token"}})
        self.assertEqual(first, self.identity("claude", env))
        env["AI_STATUS_CLAUDE_CREDENTIALS"] = json.dumps({"accessToken": "another-keychain-token"})
        self.assertNotEqual(first, self.identity("claude", env))

    def test_known_identity_rotation_and_switch_drive_engine_correctly(self):
        with patch.object(notifications.paths, "CONFIG_DIR", self.root / "settings"):
            self.write(".codex/auth.json", {"tokens": {"access_token": "old-token", "account_id": "account-one"}})
            entry = dict(provider="Codex", _dir="codex", _observed_at=1000, _fingerprint="old-context",
                         _notification_identity=self.identity("codex"), metrics=[dict(type="weekly", percentage=100)])
            events = []
            def deliver(event):
                events.append(event)
                return True
            notifications.process([entry], deliver, now=1000)
            self.write(".codex/auth.json", {"tokens": {"access_token": "refreshed-token", "account_id": "account-one"}})
            entry.update(_notification_identity=self.identity("codex"), _fingerprint="new-context", _observed_at=1001)
            notifications.process([entry], deliver, now=1001)
            self.assertEqual(len(events), 1)
            self.write(".codex/auth.json", {"tokens": {"access_token": "other-token", "account_id": "account-two"}})
            entry.update(_notification_identity=self.identity("codex"), _fingerprint="other-context", _observed_at=1002,
                         metrics=[dict(type="weekly", percentage=0)])
            notifications.process([entry], deliver, now=1002)
            self.assertEqual(len(events), 1)
            entry.update(_observed_at=1003, metrics=[dict(type="weekly", percentage=100)])
            notifications.process([entry], deliver, now=1003)
            self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
