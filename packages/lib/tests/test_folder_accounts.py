import base64
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from core import accounts, folder_accounts, config


class FolderAccountDiscoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status folder accounts ")
        self.addCleanup(temporary.cleanup)
        # Discovery reports real paths: Windows expands 8.3 names, macOS /var is /private/var.
        self.home = Path(os.path.realpath(temporary.name))
        for target, key, value in (
            (config, "CONFIG_DIR", str(self.home / "config/ai-status")),
            (config, "CONFIG_FILE", str(self.home / "config/ai-status/providers.json")),
        ):
            item = patch.object(target, key, value)
            item.start()
            self.addCleanup(item.stop)
        providers = patch.object(config, "available_providers", return_value=["claude", "codex", "commandcode"])
        providers.start()
        self.addCleanup(providers.stop)
        # Only the default Claude connection is on; tests turn on the others they need.
        config.save_config(["claude"])
        env = patch.dict(os.environ, {"HOME": str(self.home)}, clear=True)
        env.start()
        self.addCleanup(env.stop)
        folder_accounts._memo.clear()

    def login(self, folder, email, uuid=None, expires=None, meta=None):
        directory = self.home / folder
        directory.mkdir(parents=True, exist_ok=True)
        expires = expires if expires is not None else (time.time() + 3600) * 1000
        (directory / ".credentials.json").write_text(json.dumps(
            {"claudeAiOauth": {"accessToken": "token-" + email, "expiresAt": expires}}), encoding="utf-8")
        (meta or directory / ".claude.json").write_text(json.dumps(
            {"oauthAccount": {"accountUuid": uuid or "uuid-" + email, "emailAddress": email}}), encoding="utf-8")
        return directory

    def codex(self, folder, email, user, workspace="workspace", refreshed="2026-10-01T00:00:00Z"):
        directory = self.home / folder
        directory.mkdir(parents=True, exist_ok=True)
        claims = {"email": email, "https://api.openai.com/auth": {"chatgpt_user_id": user, "chatgpt_account_id": workspace}}
        id_token = "e30." + base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=") + ".sig"
        (directory / "auth.json").write_text(json.dumps({"tokens": {
            "access_token": "token-" + user, "id_token": id_token, "account_id": workspace},
            "last_refresh": refreshed}), encoding="utf-8")
        return directory

    def commandcode(self, folder, key):
        directory = self.home / folder
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "auth.json").write_text(json.dumps({"apiKey": key}), encoding="utf-8")
        return directory

    def seats(self, *slugs):
        """A seats store with `~/.claude` linked to the first seat."""
        for slug in slugs:
            self.login(f".config/seats/claude/{slug}", f"{slug}@example.com")
        os.symlink(self.home / ".config/seats/claude" / slugs[0], self.home / ".claude")

    def labels(self, provider="claude"):
        folder_accounts._memo.clear()
        return [record["label"] for record in config.discovered_accounts() if record["provider"] == provider]

    def test_a_single_claude_folder_adds_nothing(self):
        self.login(".claude", "solo@example.com", meta=self.home / ".claude.json")
        self.assertEqual(self.labels(), [])

    def test_a_single_claude_folder_turned_off_stays_off(self):
        self.login(".claude", "solo@example.com", meta=self.home / ".claude.json")
        config.save_config([])
        self.assertEqual(self.labels(), [])
        self.assertEqual(config.enabled_connection_order(), [])

    def test_seats_store_adds_every_seat_but_the_one_claude_reads(self):
        self.seats("primary", "work", "side")
        self.assertEqual(self.labels(), ["side@example.com", "work@example.com"])
        ids = config.enabled_connection_order()
        self.assertEqual(len(ids), 3)
        self.assertEqual(ids[0], "claude")

    def test_the_active_seat_is_listed_when_the_default_connection_is_off(self):
        self.seats("primary", "work")
        config.save_config([])
        self.assertEqual(self.labels(), ["primary@example.com", "work@example.com"])

    def test_hand_made_config_folders_and_claude_config_dir(self):
        # Claude Code run without CLAUDE_CONFIG_DIR keeps the account next to the folder.
        self.login(".claude", "solo@example.com", meta=self.home / ".claude.json")
        self.login(".claude-work", "work@example.com")
        self.login("elsewhere/claude", "env@example.com")
        self.login(".claude-work.bak", "backup@example.com")
        with patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home / "elsewhere/claude")}):
            # CLAUDE_CONFIG_DIR is what the default connection reads, so ~/.claude becomes an extra login.
            self.assertEqual(self.labels(), ["solo@example.com", "work@example.com"])

    def test_a_saved_account_for_the_same_file_wins(self):
        self.seats("primary", "work")
        accounts.save_document({"accounts": [{"id": "mine", "provider": "claude", "label": "Work",
                                              "auth_file": str(self.home / ".config/seats/claude/work/.credentials.json")}]},
                               config.accounts_file())
        self.assertEqual(self.labels(), [])
        self.assertEqual(config.enabled_connection_order(), ["claude", "account:mine"])

    def test_a_renamed_folder_keeps_its_id(self):
        self.seats("primary", "work")
        before = config.discovered_accounts()[0]
        (self.home / ".config/seats/claude/work").rename(self.home / ".config/seats/claude/2")
        folder_accounts._memo.clear()
        after = config.discovered_accounts()[0]
        self.assertEqual(after["id"], before["id"])
        self.assertEqual(after["auth_file"], str(self.home / ".config/seats/claude/2/.credentials.json"))

    def test_the_same_account_in_two_folders_keeps_the_freshest_login(self):
        self.login(".claude", "solo@example.com")
        self.login(".claude-old", "work@example.com", uuid="same", expires=1000)
        self.login(".claude-new", "work@example.com", uuid="same")
        [record] = config.discovered_accounts()
        self.assertEqual(record["auth_file"], str(self.home / ".claude-new/.credentials.json"))

    def test_signed_out_folders_are_skipped(self):
        self.seats("primary")
        (self.home / ".config/seats/claude/gone").mkdir(parents=True)
        self.assertEqual(self.labels(), [])

    def test_turning_one_off_saves_it_disabled_and_follows_a_rename(self):
        self.seats("primary", "work", "side")
        side, work = config.discovered_accounts()
        config.save_connection_order(["claude", "account:" + work["id"]])
        saved = accounts.load_document(config.accounts_file())["accounts"]
        self.assertEqual([(record["id"], record["enabled"]) for record in saved], [(side["id"], False)])
        folder_accounts._memo.clear()
        self.assertEqual(config.enabled_connection_order(), ["claude", "account:" + work["id"]])

        (self.home / ".config/seats/claude/side").rename(self.home / ".config/seats/claude/3")
        folder_accounts._memo.clear()
        record = config.connection_info("account:" + side["id"])
        self.assertFalse(record["enabled"])
        self.assertEqual(record["auth_file"], str(self.home / ".config/seats/claude/3/.credentials.json"))
        self.assertNotIn("account:" + side["id"], config.enabled_connection_order())

    def test_codex_seats_by_user_and_workspace(self):
        config.save_config(["codex"])
        self.codex(".config/seats/codex/primary", "me@example.com", "user-me")
        self.codex(".config/seats/codex/team", "me@example.com", "user-me", workspace="team")
        self.codex(".codex-other", "other@example.com", "user-other")
        os.symlink(self.home / ".config/seats/codex/primary", self.home / ".codex")
        self.assertEqual(self.labels("codex"), ["me@example.com", "other@example.com"])
        [team] = [record for record in config.discovered_accounts() if record["provider"] == "codex"
                  and record["auth_file"].endswith(os.path.join("team", "auth.json"))]
        self.assertTrue(team["id"].startswith("codex-"))

    def test_codex_same_login_twice_keeps_the_latest_refresh(self):
        config.save_config(["codex"])
        self.codex(".codex", "solo@example.com", "user-solo")
        self.codex(".codex-old", "me@example.com", "user-me", refreshed="2026-01-01T00:00:00Z")
        self.codex(".codex-new", "me@example.com", "user-me", refreshed="2026-10-01T00:00:00Z")
        [record] = [record for record in config.discovered_accounts() if record["provider"] == "codex"]
        self.assertEqual(record["auth_file"], str(self.home / ".codex-new/auth.json"))

    def test_commandcode_folders_are_labeled_by_name(self):
        config.save_config(["commandcode"])
        self.commandcode(".commandcode", "key-default")
        self.commandcode(".config/seats/commandcode/work", "key-work")
        self.commandcode(".commandcode-side", "key-side")
        self.assertEqual(self.labels("commandcode"), ["side", "work"])
        ids = [record["id"] for record in config.discovered_accounts()]
        self.assertTrue(all("key-" not in identity for identity in ids))

    def test_discovered_accounts_query_their_own_credentials(self):
        self.seats("primary", "work")
        [connection] = [item for item in config.enabled_connections() if item.get("account_id")]
        env, _, _ = accounts.prepare(connection)
        self.assertEqual(env["AI_STATUS_AUTH_FILE"], str(self.home / ".config/seats/claude/work/.credentials.json"))
        self.assertEqual(env["AI_STATUS_ACCOUNT_ID"], connection["account_id"])


if __name__ == "__main__":
    unittest.main()
