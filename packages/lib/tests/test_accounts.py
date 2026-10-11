import contextlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from core import accounts, cli, config, fetch, paths, state


class AccountTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status accounts ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.providers = self.root / "providers"
        self.providers.mkdir()
        self.provider = self.providers / "codex"
        self.provider.mkdir()
        (self.provider / "query.py").write_text(
            "import json, os\nfrom pathlib import Path\n"
            "if Path(__file__).with_name('fail').exists():\n"
            " print(json.dumps({'_ai_status_error':'Unavailable '+os.environ.get('TEST_TOKEN','')}))\n"
            "else:\n"
            " options=json.loads(os.environ.get('AI_STATUS_ACCOUNT_OPTIONS','{}'))\n"
            " print(json.dumps({'provider':'Test','metrics':[{'percentage':options.get('usage',25),"
            "'detail':os.environ.get('TEST_TOKEN','okay')}]}))\n", encoding="utf-8")
        for target, key, value in (
            (config, "CONFIG_DIR", str(self.root / "config")),
            (config, "CONFIG_FILE", str(self.root / "config/providers.json")),
            (fetch, "CACHE_DIR", str(self.root / "cache")),
            (fetch, "MIN_SERVICE_INTERVAL", 0),
            (state, "CACHE_FILE", str(self.root / "usage.json")),
            (state, "SELECTED_FILE", str(self.root / "selected.json")),
        ):
            item = patch.object(target, key, value)
            item.start()
            self.addCleanup(item.stop)
        provider_patch = patch.object(config, "providers_dir", return_value=str(self.providers))
        provider_patch.start()
        self.addCleanup(provider_patch.stop)
        refresh_patch = patch.object(state, "trigger_refresh")
        refresh_patch.start()
        self.addCleanup(refresh_patch.stop)
        env = patch.dict(os.environ, {"HOME": str(self.root), "CODEX_HOME": str(self.root / "codex"),
                                     "PERSONAL_TOKEN": "private-personal-token", "WORK_TOKEN": "private-work-token"})
        env.start()
        self.addCleanup(env.stop)

    def save(self, records, **extra):
        accounts.save_document({"accounts": records, **extra}, config.accounts_file())

    def record(self, account_id, usage=20, **extra):
        return {"id": account_id, "provider": "codex", "label": account_id.title(),
                "options": {"usage": usage}, **extra}

    def age_success_cache(self):
        for path in Path(fetch.CACHE_DIR).glob("*.json"):
            if path.name.endswith(".cooldown.json"):
                continue
            data = json.loads(path.read_text())
            data["timestamp"] = time.time() - fetch.MIN_REFRESH_SECONDS - 1
            paths.atomic_json(path, data)

    def run_cli(self, arguments, stdin=""):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), patch.object(sys, "stdin", io.StringIO(stdin)):
            status = cli._accounts_main(arguments)
        return status, output.getvalue(), errors.getvalue()

    def test_backwards_compatible_defaults_and_opt_in_new_providers(self):
        (self.providers / "openai").mkdir()
        self.assertEqual(config.enabled_order(), ["codex"])
        self.assertEqual(config.available_connections(), ["codex", "openai"])
        config.save_config(["openai", "codex"])
        self.assertEqual(config.enabled_connection_order(), ["openai", "codex"])
        config.save_config([])
        self.assertEqual(fetch.fetch_all_data(), [])

    def test_explicit_accounts_run_with_disabled_default_and_keep_identity(self):
        config.save_config([])
        self.save([self.record("personal", 11, env={"TEST_TOKEN": "PERSONAL_TOKEN"}),
                   self.record("work", 71, env={"TEST_TOKEN": {"from_env": "WORK_TOKEN"}})])
        data = fetch.fetch_all_data()
        self.assertEqual([p["_connection_id"] for p in data], ["account:personal", "account:work"])
        self.assertEqual([p["metrics"][0]["percentage"] for p in data], [11, 71])
        self.assertTrue(all(p["_dir"] == "codex" and p["_idx"] == 0 for p in data))
        self.assertEqual(data[1]["_account_label"], "Work")
        self.assertNotIn("private-", json.dumps(data))
        self.assertNotIn("TEST_TOKEN", os.environ)

    def test_no_account_count_cap_and_mixed_saved_order(self):
        self.save([self.record(f"account-{index}", index) for index in range(96)])
        config.save_connection_order(["account:account-95", "codex", "account:account-0"])
        self.assertEqual(config.enabled_connection_order(), ["account:account-95", "codex", "account:account-0"])
        self.assertEqual(len(config.load_accounts()), 96)
        self.assertEqual(config.connection_info("account:account-95")["provider"], "codex")
        self.assertFalse(config.connection_info("account:account-1")["enabled"])
        # Enable all and collect without starting 96 subprocesses in this test.
        config.save_connection_order(["account:account-" + str(index) for index in range(96)])
        with patch.object(fetch, "run_provider", side_effect=lambda directory, connection: {
            "provider": "Test", "metrics": [{"percentage": connection["options"]["usage"]}]
        }):
            data = fetch.fetch_all_data()
        self.assertEqual(len(data), 96)
        self.assertEqual(len({provider["_connection_id"] for provider in data}), 96)

    def test_cache_isolated_by_identity_options_and_rotated_credentials(self):
        credential = self.root / "work-auth.json"
        paths.atomic_json(credential, {"tokens": {"access_token": "first-token"}})
        personal = accounts.connection(accounts.normalize(self.record("personal", 12)))
        work = accounts.connection(accounts.normalize(self.record("work", 72, auth_file=str(credential))))
        self.assertEqual(fetch.run_provider(str(self.provider), personal)["metrics"][0]["percentage"], 12)
        self.assertEqual(fetch.run_provider(str(self.provider), work)["metrics"][0]["percentage"], 72)
        self.age_success_cache()
        (self.provider / "fail").touch()
        self.assertEqual(fetch.run_provider(str(self.provider), personal)["metrics"][0]["percentage"], 12)
        self.assertTrue(fetch.run_provider(str(self.provider), work)["_cached"])
        paths.atomic_json(credential, {"tokens": {"access_token": "second-token"}})
        self.assertIn("error", fetch.run_provider(str(self.provider), work))
        personal["options"]["usage"] = 13
        self.assertIn("error", fetch.run_provider(str(self.provider), personal))

    def test_default_cache_context_tracks_credential_files_and_rejects_legacy(self):
        credential = self.root / "codex/auth.json"
        paths.atomic_json(credential, {"tokens": {"access_token": "first-token"}})
        old_path = Path(fetch.CACHE_DIR) / "codex.json"
        paths.atomic_json(old_path, {"timestamp": __import__("time").time(), "data": {"provider": "Other user", "metrics": [{"percentage": 99}]}})
        (self.provider / "fail").touch()
        self.assertIn("error", fetch.run_provider(str(self.provider)))
        (self.provider / "fail").unlink()
        fetch.run_provider(str(self.provider))
        self.age_success_cache()
        (self.provider / "fail").touch()
        self.assertTrue(fetch.run_provider(str(self.provider))["_cached"])
        paths.atomic_json(credential, {"tokens": {"access_token": "rotated-token"}})
        self.assertIn("error", fetch.run_provider(str(self.provider)))

    def test_missing_secret_reference_never_queries_or_reuses_cache(self):
        connection = accounts.connection(accounts.normalize(self.record("work", env={"TEST_TOKEN": {"from_env": "DOES_NOT_EXIST_123456"}})))
        with patch.object(fetch.subprocess, "run") as run:
            result = fetch.run_provider(str(self.provider), connection)
        run.assert_not_called()
        self.assertIn("unset or empty", result["error"])
        self.assertNotIn("DOES_NOT_EXIST", result["error"])

    def test_account_failure_callbacks_and_include_errors_are_independent(self):
        config.save_config([])
        self.save([self.record("good"), self.record("bad", env={"TEST_TOKEN": "MISSING_SECRET_123456"})])
        errors, callbacks = {}, {}
        data = fetch.fetch_all_data(on_error=lambda identity, error: errors.update({identity: error}),
                                    on_result=lambda identity, result: callbacks.update({identity: result}))
        self.assertEqual(list(errors), ["account:bad"])
        self.assertEqual(data[0]["_connection_id"], "account:good")
        self.assertIsNone(callbacks["account:bad"])
        data = fetch.fetch_all_data(include_errors=True)
        self.assertEqual(data[1]["_connection_id"], "account:bad")
        self.assertEqual(data[1]["metrics"], [])
        self.assertIn("_error", data[1])

    def test_config_and_cache_files_are_private_and_errors_redact_credentials(self):
        record = self.record("personal", env={"TEST_TOKEN": "PERSONAL_TOKEN"})
        self.save([record])
        connection = config.enabled_connections()[-1]
        fetch.run_provider(str(self.provider), connection)
        self.age_success_cache()
        (self.provider / "fail").touch()
        result = fetch.run_provider(str(self.provider), connection)
        self.assertNotIn("private-personal-token", json.dumps(result))
        self.assertIn("[redacted]", result["_error"])
        for cache in Path(fetch.CACHE_DIR).glob("*.json"):
            self.assertNotIn("private-personal-token", cache.read_text())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o600)
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(Path(config.accounts_file()).stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(Path(fetch.CACHE_DIR).stat().st_mode), 0o700)

    def test_cli_add_edit_list_remove_with_stdin_and_secret_references(self):
        record = self.record("work", env={"TEST_TOKEN": "WORK_TOKEN"}, options={"usage": 20, "region": "test-region"})
        result, output, errors = self.run_cli(["add", "--file", "-"], json.dumps(record))
        self.assertEqual((result, errors), (0, ""))
        result, output, errors = self.run_cli(["list", "--saved", "--json"])
        public = json.loads(output)
        self.assertEqual(public[0]["env"], {"TEST_TOKEN": {"from_env": "WORK_TOKEN"}})
        self.assertNotIn("test-region", output)
        self.assertEqual(public[0]["option_keys"], ["region", "usage"])
        self.assertEqual(self.run_cli(["edit", "work", "--label", "Office", "--disabled"])[0], 0)
        self.assertFalse(config.load_accounts()[0]["enabled"])
        self.assertEqual(config.load_accounts()[0]["options"]["region"], "test-region")
        self.assertEqual(self.run_cli(["remove", "work"])[0], 0)
        self.assertEqual(config.load_accounts(), [])

    def test_list_discovers_default_codex_from_shared_collector_cache_without_collecting(self):
        config.save_config(["codex"])
        self.save([self.record("work", 42, env={"TEST_TOKEN": "WORK_TOKEN"})])
        data = fetch.fetch_all_data(include_errors=True)
        state.save_cache(data)
        self.assertEqual({entry["_connection_id"] for entry in data}, {"codex", "account:work"})
        previous = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        with patch.object(fetch, "fetch_all_data", side_effect=AssertionError("List must reuse the shared cache")), \
                patch.object(accounts, "prepare", side_effect=AssertionError("List must not resolve credentials")):
            result, output, errors = self.run_cli(["list", "--json"])
            saved_result, saved_output, saved_errors = self.run_cli(["list", "--saved", "--json"])
        self.assertEqual((result, errors, saved_result, saved_errors), (0, "", 0, ""))
        rows = {row["connection_id"]: row for row in json.loads(output)}
        self.assertEqual(set(rows), {"codex", "account:work"})
        self.assertEqual((rows["codex"]["source"], rows["codex"]["label"], rows["codex"]["usage_status"]),
                         ("default", "Default", "available"))
        self.assertEqual(rows["account:work"]["source"], "saved")
        self.assertEqual(rows["account:work"]["usage_status"], "available")
        self.assertEqual(json.loads(saved_output), [accounts.public_record(config.load_accounts()[0])])
        after = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        self.assertEqual(after, previous)

    def test_cli_rejects_literal_secrets_and_leaves_previous_file_intact(self):
        self.save([self.record("existing")])
        before = Path(config.accounts_file()).read_bytes()
        status, output, error = self.run_cli(["add", "--file", "-"], json.dumps(self.record("bad", env={"TEST_TOKEN": {"value": "never-print-this"}})))
        self.assertEqual(status, 1)
        self.assertNotIn("never-print-this", error)
        status, output, error = self.run_cli(["add", "--file", "-"], json.dumps(self.record("bad-options", options={"access_token": "never-print-this"})))
        self.assertEqual(status, 1)
        self.assertNotIn("never-print-this", error)
        self.assertEqual(Path(config.accounts_file()).read_bytes(), before)
        status, output, error = self.run_cli(["add", "--file", "-"], '{"token":"never-print-this"')
        self.assertEqual(status, 1)
        self.assertNotIn("never-print-this", error)

    def test_account_selection_and_metric_cycle_do_not_cross_accounts(self):
        self.save([self.record("personal"), self.record("work")])
        config.save_connection_order(["account:personal", "account:work"])
        state.save_cache([
            {"_dir": "codex", "_connection_id": "account:personal", "_idx": 0, "metrics": [{"type": "rolling", "percentage": 20}]},
            {"_dir": "codex", "_connection_id": "account:work", "_idx": 0, "metrics": [{"type": "weekly", "percentage": 70}]},
        ])
        state.save_selected({"provider": "account:personal", "idx": 0, "metric": "rolling"})
        cli.scroll_down("quickshell")
        self.assertEqual(state.load_selected()["provider"], "account:work")
        self.assertEqual(state.load_selected()["metric"], "weekly")

    def test_invalid_account_document_does_not_stop_existing_default(self):
        path = Path(config.accounts_file())
        path.parent.mkdir()
        path.write_text('{"version":1,"accounts":[{"token":"do-not-echo"}]}', encoding="utf-8")
        errors = {}
        result = fetch.fetch_all_data(on_error=lambda identity, error: errors.update({identity: error}))
        self.assertEqual(result[0]["_connection_id"], "codex")
        self.assertIn("accounts", errors)
        self.assertNotIn("do-not-echo", json.dumps(errors))

    def test_explicit_auth_never_inherits_primary_credentials_or_context(self):
        connection = accounts.connection(accounts.normalize({"id": "work", "provider": "anthropic-api",
                                                              "env": {"ANTHROPIC_ADMIN_KEY": "WORK_KEY"}}))
        environment = {"HOME": str(self.root), "ANTHROPIC_ADMIN_TOKEN": "primary-oauth-token",
                       "ANTHROPIC_ADMIN_KEY": "primary-admin-key", "WORK_KEY": "explicit-work-key"}
        actual, fingerprint, secrets = accounts.prepare(connection, environment)
        self.assertNotIn("ANTHROPIC_ADMIN_TOKEN", actual)
        self.assertEqual(actual["ANTHROPIC_ADMIN_KEY"], "explicit-work-key")
        environment["ANTHROPIC_ADMIN_TOKEN"] = "another-primary-token"
        self.assertEqual(accounts.prepare(connection, environment)[1], fingerprint)
        codex = accounts.connection(accounts.normalize(self.record("empty")))
        actual = accounts.prepare(codex, {"HOME": str(self.root), "CODEX_HOME": "/primary/codex", "CODEX_ACCESS_TOKEN": "primary-token"})[0]
        self.assertNotIn("CODEX_HOME", actual)
        self.assertNotIn("CODEX_ACCESS_TOKEN", actual)
        google = accounts.connection(accounts.normalize({"id": "google-work", "provider": "google-cloud", "options": {"gcloud_account": "work@example.com"}}))
        self.assertEqual(accounts.prepare(google, {"CLOUDSDK_CONFIG": str(self.root / "named-gcloud")})[0]["CLOUDSDK_CONFIG"], str(self.root / "named-gcloud"))

    def test_rate_limit_cooldown_persists_skips_and_retries_after_expiry(self):
        connection = accounts.connection(accounts.normalize(self.record("work")))
        response = subprocess.CompletedProcess([], 0, json.dumps({"_ai_status_error": "Too Many Requests",
            "_ai_status_status": 429, "_ai_status_retry_after": 10}), "")
        with patch.object(fetch.time, "time", return_value=1000), patch.object(fetch.subprocess, "run", return_value=response) as run:
            result = fetch.run_provider(str(self.provider), connection)
            self.assertEqual(run.call_count, 1)
            self.assertIn("next attempt in 10 seconds", result["error"])
            result = fetch.run_provider(str(self.provider), connection)
            self.assertEqual(run.call_count, 1)
            self.assertIn("next attempt in 10 seconds", result["error"])
        self.assertEqual(len(list(Path(fetch.CACHE_DIR).glob("*.cooldown.json"))), 1)
        # No in-memory cooldown state is required, including after process restart.
        with patch.object(fetch.time, "time", return_value=1005), patch.object(fetch.subprocess, "run") as run:
            self.assertIn("next attempt in 5 seconds", fetch.run_provider(str(self.provider), connection)["error"])
            run.assert_not_called()
        success = subprocess.CompletedProcess([], 0, '{"provider":"Test","metrics":[{"percentage":20}]}', "")
        with patch.object(fetch.time, "time", return_value=1011), patch.object(fetch.subprocess, "run", return_value=success) as run:
            self.assertEqual(fetch.run_provider(str(self.provider), connection)["metrics"][0]["percentage"], 20)
            run.assert_called_once()

    def test_rate_limit_uses_cached_usage_and_isolates_other_accounts_and_keys(self):
        personal = accounts.connection(accounts.normalize(self.record("personal", env={"TEST_TOKEN": "PERSONAL_TOKEN"})))
        work = accounts.connection(accounts.normalize(self.record("work", 77, env={"TEST_TOKEN": "WORK_TOKEN"})))
        response = subprocess.CompletedProcess([], 0, '{"_ai_status_error":"429","_ai_status_status":429}', "")
        with patch.object(fetch.time, "time", return_value=939):
            fetch._save_cache(str(self.provider), {"provider": "Test", "metrics": [{"percentage": 14}]}, personal)
        with patch.object(fetch.time, "time", return_value=1000):
            with patch.object(fetch.subprocess, "run", return_value=response):
                result = fetch.run_provider(str(self.provider), personal)
            self.assertTrue(result["_cached"])
            self.assertEqual(result["metrics"][0]["percentage"], 14)
            self.assertIn("300 seconds", result["_error"])
            self.assertEqual(fetch._cooldown_remaining(work, accounts.prepare(work)[1]), 0)
            with patch.dict(os.environ, {"WORK_TOKEN": "new-work-token"}):
                with patch.object(fetch.subprocess, "run") as run:
                    self.assertTrue(fetch.run_provider(str(self.provider), personal)["_cached"])
                    run.assert_not_called()
            with patch.dict(os.environ, {"PERSONAL_TOKEN": "new-personal-token"}):
                self.assertEqual(fetch._cooldown_remaining(personal, accounts.prepare(personal)[1]), 0)

    def test_queries_for_one_service_run_sequentially(self):
        active, maximum = 0, 0
        counter = threading.Lock()
        def query(*arguments, **keywords):
            nonlocal active, maximum
            with counter:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.01)
            with counter:
                active -= 1
            return subprocess.CompletedProcess([], 0, '{"provider":"Test","metrics":[{"percentage":20}]}', "")
        with patch.object(fetch.subprocess, "run", side_effect=query), ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(fetch.run_provider, str(self.provider), accounts.connection(accounts.normalize(self.record(str(index))))) for index in range(4)]
            self.assertTrue(all(future.result().get("metrics") for future in futures))
        self.assertEqual(maximum, 1)

    def test_success_refresh_floor_survives_restart_without_stale_markers(self):
        connection = accounts.connection(accounts.normalize(self.record("work")))
        with patch.object(fetch.time, "time", return_value=1000):
            fetch._save_cache(str(self.provider), {"provider": "Test", "metrics": [{"percentage": 22}]}, connection)
        with patch.object(fetch.time, "time", return_value=1059), patch.object(fetch.subprocess, "run") as run:
            result = fetch.run_provider(str(self.provider), connection)
            run.assert_not_called()
            self.assertEqual(result["metrics"][0]["percentage"], 22)
            self.assertNotIn("_cached", result)
            self.assertNotIn("_error", result)
        response = subprocess.CompletedProcess([], 0, '{"provider":"Test","metrics":[{"percentage":23}]}', "")
        with patch.object(fetch.time, "time", return_value=1060), patch.object(fetch.subprocess, "run", return_value=response) as run:
            self.assertEqual(fetch.run_provider(str(self.provider), connection)["metrics"][0]["percentage"], 23)
            run.assert_called_once()

    def test_service_start_pacing_is_shared_for_vendor_adapters(self):
        previous = dict(fetch._SERVICE_LAST_START)
        self.addCleanup(lambda: (fetch._SERVICE_LAST_START.clear(), fetch._SERVICE_LAST_START.update(previous)))
        fetch._SERVICE_LAST_START.clear()
        with patch.object(fetch, "MIN_SERVICE_INTERVAL", 1), patch.object(fetch.time, "monotonic", side_effect=[100, 100, 100.2, 101]), patch.object(fetch.time, "sleep") as sleep:
            fetch._pace_service("claude")
            fetch._pace_service("anthropic-api")
        self.assertAlmostEqual(sleep.call_args.args[0], 0.8)

    def test_unknown_default_antigravity_keyring_identity_never_reuses_cache(self):
        environment = patch.dict(os.environ, {"ANTIGRAVITY_ACCESS_TOKEN": ""})
        environment.start()
        self.addCleanup(environment.stop)
        directory = self.providers / "antigravity"
        directory.mkdir()
        (directory / "query.py").write_text("print('{}')", encoding="utf-8")
        fetch._save_cache(str(directory), {"provider": "Previous login", "metrics": [{"percentage": 99}]})
        success = subprocess.CompletedProcess([], 0, '{"provider":"Current login","metrics":[{"percentage":20}]}', "")
        with patch.object(fetch.subprocess, "run", return_value=success) as run:
            result = fetch.run_provider(str(directory))
        run.assert_called_once()
        self.assertEqual(result["metrics"][0]["percentage"], 20)
        failure = subprocess.CompletedProcess([], 0, '{"_ai_status_error":"Usage unavailable"}', "")
        with patch.object(fetch.subprocess, "run", return_value=failure):
            result = fetch.run_provider(str(directory))
        self.assertEqual(result, {"error": "Usage unavailable"})

    def test_sqlite_auth_fingerprints_preserve_cooldown_across_unrelated_wal_writes(self):
        for name in ("kiro", "cursor"):
            with self.subTest(provider=name):
                database = self.root / (name + ".sqlite3")
                writer = sqlite3.connect(database)
                self.addCleanup(writer.close)
                writer.execute("PRAGMA journal_mode=WAL")
                writer.execute("PRAGMA wal_autocheckpoint=0")
                if name == "kiro":
                    writer.execute("CREATE TABLE auth_kv (key TEXT PRIMARY KEY, value TEXT)")
                    writer.execute("CREATE TABLE state (key TEXT PRIMARY KEY, value TEXT)")
                    writer.execute("INSERT INTO auth_kv VALUES (?, ?)", ("kirocli:odic:token", '{"access_token":"original-token","region":"us-east-1"}'))
                    writer.execute("INSERT INTO state VALUES (?, ?)", ("api.codewhisperer.profile", '{"arn":"original-profile"}'))
                    writer.execute("INSERT INTO state VALUES (?, ?)", ("chat.history", "before"))
                else:
                    writer.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
                    writer.execute("INSERT INTO ItemTable VALUES (?, ?)", ("cursorAuth/accessToken", "original-token"))
                    writer.execute("INSERT INTO ItemTable VALUES (?, ?)", ("workbench.windowState", "before"))
                writer.commit()
                record = accounts.connection(accounts.normalize({"id": name + "-work", "provider": name, "auth_file": str(database)}))
                first = accounts.prepare(record)[1]
                with patch.object(fetch.time, "time", return_value=1000):
                    fetch._save_cooldown(record, first, 300)
                if name == "kiro":
                    writer.execute("UPDATE state SET value='after' WHERE key='chat.history'")
                else:
                    writer.execute("UPDATE ItemTable SET value='after' WHERE key='workbench.windowState'")
                writer.commit()
                self.assertEqual(accounts.prepare(record)[1], first)
                with patch.object(fetch.time, "time", return_value=1001), patch.object(fetch.subprocess, "run") as run:
                    self.assertIn("299 seconds", fetch.run_provider(str(self.provider), record)["error"])
                run.assert_not_called()
                if name == "kiro":
                    writer.execute("UPDATE auth_kv SET value=? WHERE key=?", ('{"access_token":"rotated-token","region":"us-east-1"}', "kirocli:odic:token"))
                else:
                    writer.execute("UPDATE ItemTable SET value=? WHERE key=?", ("rotated-token", "cursorAuth/accessToken"))
                writer.commit()
                rotated = accounts.prepare(record)[1]
                self.assertNotEqual(rotated, first)
                with patch.object(fetch.time, "time", return_value=1001):
                    self.assertEqual(fetch._cooldown_remaining(record, rotated), 0)
                if name == "kiro":
                    writer.execute("UPDATE state SET value=? WHERE key=?", ('{"arn":"another-profile"}', "api.codewhisperer.profile"))
                    writer.commit()
                    profile = accounts.prepare(record)[1]
                    self.assertNotEqual(profile, rotated)
                    writer.execute("UPDATE auth_kv SET value=? WHERE key=?", ('{"access_token":"rotated-token","region":"eu-west-1"}', "kirocli:odic:token"))
                    writer.commit()
                    self.assertNotEqual(accounts.prepare(record)[1], profile)


if __name__ == "__main__":
    unittest.main()
