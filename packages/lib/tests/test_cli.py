"""Exercise CLI help, safe account listings and existing desktop contracts."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock, patch

LIB = Path(__file__).resolve().parents[1]
SRC = LIB / "src"
ENTRYPOINT = SRC / "bin" / "ai-status"
sys.path.insert(0, str(SRC))
import core
from core import __version__, accounts, cli, config, daemon, fetch, macos, paths, provider_http, state


class CLIEntrypointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status cli ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        guards = self.root / "guards"
        guards.mkdir()
        self.effects = self.root / "unexpected-effects"
        # Help must not start collectors, desktop libraries or HTTP requests,
        # even when an implementation catches the resulting error internally.
        (guards / "sitecustomize.py").write_text(
            "import builtins, os, socket, subprocess, urllib.request\n"
            "from pathlib import Path\n"
            "def forbidden(*args, **kwargs):\n"
            " Path(os.environ['AI_STATUS_TEST_EFFECTS']).write_text('side effect')\n"
            " raise RuntimeError('Help invoked a desktop, collector or network operation')\n"
            "subprocess.Popen = forbidden\n"
            "socket.socket.connect = forbidden\n"
            "socket.create_connection = forbidden\n"
            "urllib.request.urlopen = forbidden\n"
            "original_import = builtins.__import__\n"
            "def guarded_import(name, *args, **kwargs):\n"
            " if name == 'PySide6' or name.startswith('PySide6.'):\n"
            "  forbidden()\n"
            " return original_import(name, *args, **kwargs)\n"
            "builtins.__import__ = guarded_import\n",
            encoding="utf-8",
        )
        self.environment = {
            **os.environ,
            "HOME": str(self.home),
            "USERPROFILE": str(self.home),
            "APPDATA": str(self.home / "AppData/Roaming"),
            "LOCALAPPDATA": str(self.home / "AppData/Local"),
            "XDG_CONFIG_HOME": str(self.home / ".config"),
            "XDG_CACHE_HOME": str(self.home / ".cache"),
            "XDG_DATA_HOME": str(self.home / ".local/share"),
            "CODEX_HOME": str(self.home / ".codex"),
            "CLAUDE_CONFIG_DIR": str(self.home / ".claude"),
            "PYTHONPATH": str(guards),
            "PYTHONDONTWRITEBYTECODE": "1",
            "AI_STATUS_TEST_EFFECTS": str(self.effects),
        }

    def snapshot(self):
        return {
            str(path.relative_to(self.home)): path.read_bytes() if path.is_file() else None
            for path in self.home.rglob("*")
        }

    def invoke(self, *arguments, entrypoint=ENTRYPOINT):
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, str(entrypoint), *arguments],
            env=self.environment, cwd=self.root, capture_output=True,
            text=True, encoding="utf-8", timeout=10,
        )
        self.assertEqual(self.snapshot(), before, (arguments, result.stderr))
        self.assertFalse(self.effects.exists(), (arguments, result.stdout, result.stderr))
        self.assertNotIn("Traceback", result.stderr)
        return result

    def assert_help(self, result, *details):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("usage:", result.stdout.lower())
        for detail in details:
            self.assertIn(detail, result.stdout)

    def test_root_help_exposes_user_commands(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                self.assert_help(self.invoke(flag), "accounts", "providers", "status", "doctor", "config", "update", "--version")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Native desktops keep their no-argument launcher")
    def test_no_arguments_on_linux_prints_help_and_exits_successfully(self):
        self.assert_help(self.invoke(), "accounts", "providers", "config")

    def test_subcommand_help_and_help_command_are_equivalent(self):
        cases = {
            "config": ("--usage-display", "used", "remaining", "without opening Settings"),
            "accounts": ("add", "edit", "list", "remove", "--saved", "--refresh"),
            "providers": ("--json",),
            "status": ("status",),
            "doctor": ("doctor", "JSON"),
            "update": ("optional update", "terminal", "checksummed installer"),
        }
        for command, details in cases.items():
            with self.subTest(command=command):
                direct = self.invoke(command, "--help")
                alias = self.invoke("help", command)
                self.assert_help(direct, *details)
                self.assert_help(alias, *details)
                self.assertEqual(direct.stdout, alias.stdout)

    def test_accounts_add_help_describes_credential_references(self):
        direct = self.invoke("accounts", "add", "--help")
        self.assert_help(direct, "--auth-file", "--env", "SOURCE_ENV", "--id", "--label")
        alias = self.invoke("help", "accounts", "add")
        self.assert_help(alias)
        self.assertEqual(direct.stdout, alias.stdout)

    def test_all_desktop_integration_commands_have_help_without_launching(self):
        for command in ("daemon", "refresh", "config", "save-settings", "select-metric",
                        "scroll-up", "scroll-down", "cycle-metric", "logo", "revert", "tray", "macos",
                        "swiftbar", "swiftbar-stream", "swiftbar-refresh", "swiftbar-select"):
            with self.subTest(command=command):
                self.assert_help(self.invoke(command, "--help"), command)

    def test_help_does_not_read_or_rewrite_a_broken_accounts_file(self):
        directory = self.home / ".config/ai-status"
        if sys.platform == "win32":
            directory = Path(self.environment["APPDATA"]) / "ai-status"
        directory.mkdir(parents=True)
        (directory / "accounts.json").write_text("not-valid-json", encoding="utf-8")
        for arguments in (("--help",), ("accounts", "--help"), ("status", "--help"), ("doctor", "--help")):
            with self.subTest(arguments=arguments):
                self.assert_help(self.invoke(*arguments))

    def test_version_remains_machine_readable(self):
        result = self.invoke("--version")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertEqual(result.stdout.strip(), __version__)

    def test_windows_entrypoint_preserves_version_and_account_error_exit_status(self):
        version = self.invoke("--version", entrypoint=SRC / "windows.py")
        self.assertEqual((version.returncode, version.stderr), (0, ""))
        self.assertEqual(version.stdout.strip(), __version__)
        invalid = self.invoke("accounts", "remove", "missing-account", entrypoint=SRC / "windows.py")
        self.assertEqual(invalid.returncode, 1)
        self.assertEqual(invalid.stdout, "")
        self.assertIn("Unknown account ID", invalid.stderr)

    def test_bad_arguments_fail_before_any_command_runs(self):
        cases = (
            ("unknown-command",), ("--unknown-option",),
            ("status", "--unknown-option"), ("doctor", "--unknown-option"),
            ("accounts", "unknown-action"), ("accounts", "remove"),
            ("accounts", "--saved", "--refresh"),
            ("accounts", "--refresh", "remove", "work"),
            ("accounts", "--saved", "remove", "work"),
            ("daemon", "--format", "unknown-format"),
            ("refresh", "--settings-json", "{}"),
            ("status", "--format", "quickshell"), ("help", "unknown-command"),
            ("config", "--usage-display", "invalid"), ("config", "--usage-display"),
            ("status", "--usage-display", "remaining"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("usage:", result.stderr.lower())
                self.assertTrue(result.stderr.strip())
                self.assertEqual(result.stdout, "")

    def test_private_query_missing_provider_keeps_packaged_error_contract(self):
        for arguments in (("--query",), ("--query", "codex", "extra")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual(result.returncode, 1)
                self.assertIn("Usage: ai-status --query PROVIDER", result.stderr)

    def test_accounts_without_action_explains_discovery_and_next_steps(self):
        result = self.invoke("accounts")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn("ai-status accounts --refresh", result.stdout)
        self.assertIn("ai-status accounts add", result.stdout)
        self.assertIn("ai-status config", result.stdout)
        for arguments in (("accounts", "--json"), ("accounts", "list", "--json"),
                          ("accounts", "--saved", "--json"), ("accounts", "list", "--saved", "--json")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertEqual(json.loads(result.stdout), [])

    def test_providers_entrypoint_reads_collection_settings_without_authentication(self):
        directory = self.home / ".config/ai-status"
        if sys.platform == "win32":
            directory = Path(self.environment["APPDATA"]) / "ai-status"
        directory.mkdir(parents=True)
        (directory / "providers.json").write_text('["codex"]', encoding="utf-8")
        # Broken additional accounts must not prevent looking up provider IDs.
        (directory / "accounts.json").write_text("not-valid-json", encoding="utf-8")
        table = self.invoke("providers")
        self.assertEqual((table.returncode, table.stderr), (0, ""))
        self.assertIn("DEFAULT CONNECTION", table.stdout)
        self.assertIn("not authentication", table.stdout)
        result = self.invoke("providers", "--json")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        records = {record["id"]: record for record in json.loads(result.stdout)}
        self.assertTrue(records["codex"]["enabled"])
        self.assertFalse(records["openrouter"]["enabled"])
        self.assertEqual({identity for identity, record in records.items() if record["enabled"]}, {"codex"})

    def test_accounts_listing_preserves_public_json_without_resolving_secrets(self):
        credential = self.root / "credentials.json"
        credential.write_text("private-credential-content", encoding="utf-8")
        directory = self.home / ".config/ai-status"
        if sys.platform == "win32":
            directory = Path(self.environment["APPDATA"]) / "ai-status"
        directory.mkdir(parents=True)
        record = {"id": "work", "provider": "openrouter", "label": "Trabalho", "enabled": True,
                  "auth_file": str(credential), "env": {"OPENROUTER_API_KEY": {"from_env": "WORK_KEY"}},
                  "options": {"monthly_budget": 100, "project_ids": ["private-project-value"]}}
        (directory / "accounts.json").write_text(json.dumps({"version": 1, "accounts": [record]}), encoding="utf-8")
        self.environment["WORK_KEY"] = "private-environment-value"
        public = {key: record[key] for key in ("id", "provider", "label", "enabled", "auth_file", "env")}
        public["option_keys"] = ["monthly_budget", "project_ids"]
        full = {**public, "connection_id": "account:work", "source": "saved", "usage_status": "not_checked"}
        for arguments in (("accounts",), ("accounts", "list"), ("accounts", "--json"), ("accounts", "list", "--json"),
                          ("accounts", "--saved", "--json"), ("accounts", "list", "--saved", "--json"),
                          ("accounts", "--saved", "list", "--json")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                for secret in ("private-environment-value", "private-credential-content", "private-project-value"):
                    self.assertNotIn(secret, result.stdout + result.stderr)
                if "--json" in arguments:
                    self.assertEqual(json.loads(result.stdout), [public if "--saved" in arguments else full])
                else:
                    self.assertIn("ID", result.stdout)
                    self.assertIn("Trabalho", result.stdout)
                    self.assertIn("enabled", result.stdout.lower())

    def test_cached_default_codex_appears_without_an_explicit_account_file(self):
        cache = self.home / ".cache/ai-status.json"
        if sys.platform == "win32":
            cache = Path(self.environment["LOCALAPPDATA"]) / "ai-status/cache/usage.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps([{"_dir": "codex", "provider": "Codex (Pro)", "metrics": [
            {"type": "rolling", "percentage": 0}]}]), encoding="utf-8")
        expected = {"id": "codex", "provider": "codex", "label": "Default", "enabled": True,
                    "connection_id": "codex", "source": "default", "usage_status": "available"}
        for arguments in (("accounts", "--json"), ("accounts", "list", "--json")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                self.assertEqual(json.loads(result.stdout), [expected])
        table = self.invoke("accounts")
        self.assertEqual((table.returncode, table.stderr), (0, ""))
        for detail in ("default:codex", "SOURCE", "COLLECTION", "USAGE", "available"):
            self.assertIn(detail, table.stdout)
        saved = self.invoke("accounts", "--saved", "--json")
        self.assertEqual((saved.returncode, saved.stderr), (0, ""))
        self.assertEqual(json.loads(saved.stdout), [])


class CLICommandTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status cli commands ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target, name, value in (
            (paths, "CONFIG_DIR", self.root / "config"),
            (paths, "CACHE_DIR", self.root / "cache"),
            (paths, "LOG_FILE", self.root / "error.log"),
            (config, "CONFIG_FILE", str(self.root / "config/providers.json")),
            (config, "CONFIG_DIR", str(self.root / "config")),
            (state, "CACHE_FILE", str(self.root / "usage.json")),
            (state, "SELECTED_FILE", str(self.root / "config/selected.json")),
        ):
            item = patch.object(target, name, value)
            item.start()
            self.addCleanup(item.stop)
        environment = patch.dict(os.environ, {"HOME": str(self.root), "USERPROFILE": str(self.root),
                                              "CODEX_HOME": str(self.root / ".codex"),
                                              "CLAUDE_CONFIG_DIR": str(self.root / ".claude"),
                                              "XDG_DATA_HOME": str(self.root / ".local/share")})
        environment.start()
        self.addCleanup(environment.stop)

    def invoke(self, arguments, tty=False):
        class TTYOutput(io.StringIO):
            def isatty(self):
                return tty

        output, errors = TTYOutput(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            try:
                result = cli.main(arguments)
            except SystemExit as error:
                result = error.code
        return 0 if result is None else result, output.getvalue(), errors.getvalue()

    def save_usage(self, entries, age=0):
        cache = Path(state.CACHE_FILE)
        cache.write_text(json.dumps(entries), encoding="utf-8")
        if age:
            timestamp = time.time() - age
            os.utime(cache, (timestamp, timestamp))

    def usage(self, identity="codex", **changes):
        return {"_dir": "codex", "_connection_id": identity, "_idx": 0,
                "provider": "Codex (Pro)", "metrics": [{"type": "rolling", "percentage": 0}], **changes}

    def test_usage_display_config_saves_without_opening_settings_or_collecting(self):
        initial = {"provider": "account:work", "idx": 2, "metric": "weekly", "icon_mode": "logo",
                   "show_pct": False, "custom": {"preserve": True}}
        state.save_selected(initial)
        for platform, windows in (("linux", False), ("darwin", False), ("win32", True)):
            for mode in ("remaining", "used"):
                with self.subTest(platform=platform, mode=mode), \
                        patch.object(sys, "platform", platform), patch.object(paths, "IS_WINDOWS", windows), \
                        patch.object(cli.subprocess, "Popen") as launch, \
                        patch.object(macos, "launch") as native, \
                        patch.object(fetch, "fetch_all_data") as collect, \
                        patch.object(state, "trigger_refresh") as refresh:
                    result, output, errors = self.invoke(["config", "--usage-display", mode])
                self.assertEqual((result, errors), (0, ""))
                self.assertEqual(output.strip(), f"Usage display: {mode.title()}")
                self.assertEqual(state.load_selected(), {**initial, "usage_display": mode})
                launch.assert_not_called()
                native.assert_not_called()
                collect.assert_not_called()
                refresh.assert_not_called()

    def test_usage_display_config_works_without_existing_preferences(self):
        result, output, errors = self.invoke(["config", "--usage-display", "remaining", "--frontend", "quickshell"])
        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(state.load_selected(), {"usage_display": "remaining"})

    def test_invalid_usage_display_preserves_existing_preferences(self):
        initial = {"provider": "codex", "usage_display": "remaining"}
        state.save_selected(initial)
        for value in ("invalid", "", "USED"):
            with self.subTest(value=value):
                result, output, errors = self.invoke(["config", "--usage-display", value])
                self.assertEqual((result, output), (2, ""))
                self.assertIn("invalid choice", errors)
                self.assertEqual(state.load_selected(), initial)

    def test_usage_display_reports_save_failure(self):
        initial = {"provider": "codex", "usage_display": "used"}
        state.save_selected(initial)
        with patch.object(paths, "atomic_json", side_effect=OSError("Permission denied")):
            result, output, errors = self.invoke(["config", "--usage-display", "remaining"])
        self.assertEqual((result, output), (1, ""))
        self.assertIn("Unable to save", errors)
        self.assertEqual(state.load_selected(), initial)

    def test_full_accounts_keeps_default_and_saved_connection_identities_distinct(self):
        records = [accounts.normalize({"id": identity, "provider": "codex", "label": label})
                   for identity, label in (("codex", "Saved Codex"), ("work", "Work"))]
        accounts.save_document({"version": 1, "accounts": records}, config.accounts_file())
        self.save_usage([self.usage(), self.usage("account:codex", _account_id="codex"),
                         self.usage("account:work", _account_id="work")])
        with patch.object(fetch, "fetch_all_data") as query, patch.object(state, "save_cache") as save, \
                patch.object(state, "trigger_refresh") as refresh, patch.object(accounts, "prepare") as prepare:
            result, output, errors = self.invoke(["accounts", "--json"])
        self.assertEqual((result, errors), (0, ""))
        rows = json.loads(output)
        self.assertEqual({row["connection_id"] for row in rows}, {"codex", "account:codex", "account:work"})
        defaults = [row for row in rows if row["source"] == "default"]
        self.assertEqual(defaults, [{"id": "codex", "provider": "codex", "label": "Default", "enabled": True,
                                     "connection_id": "codex", "source": "default", "usage_status": "available"}])
        for record in records:
            row = next(row for row in rows if row["connection_id"] == "account:" + record["id"])
            self.assertEqual(row, {**accounts.public_record(record), "connection_id": "account:" + record["id"],
                                   "source": "saved", "usage_status": "available"})
        query.assert_not_called()
        save.assert_not_called()
        refresh.assert_not_called()
        prepare.assert_not_called()

    def test_default_discovery_accepts_legacy_cache_and_deduplicates_provider_results(self):
        legacy = self.usage()
        del legacy["_connection_id"]
        legacy.pop("_idx")
        self.save_usage([legacy, self.usage(_idx=1), self.usage(_idx=2)])
        result, output, errors = self.invoke(["accounts", "list", "--json"])
        self.assertEqual((result, errors), (0, ""))
        rows = json.loads(output)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["connection_id"], rows[0]["source"]), ("codex", "default"))

    def test_saved_usage_does_not_discover_a_default_provider_login(self):
        for entry in (self.usage("account:work"), self.usage(_account_id="work")):
            with self.subTest(entry=entry):
                self.save_usage([entry])
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                self.assertEqual(json.loads(output), [])

    def test_default_identity_matches_provider_directory_when_present(self):
        without_directory = self.usage()
        del without_directory["_dir"]
        for entry, expected in ((self.usage("openrouter"), []), (without_directory, ["codex"])):
            with self.subTest(entry=entry):
                self.save_usage([entry])
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                self.assertEqual([row["connection_id"] for row in json.loads(output)], expected)

    def test_cached_or_stale_usage_is_separate_from_current_authentication_and_collection(self):
        for entry, age in ((self.usage(_cached=True, _error="Login expired"), 0), (self.usage(), 301)):
            with self.subTest(entry=entry, age=age):
                config.save_config([])
                self.save_usage([entry], age=age)
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                rows = json.loads(output)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["usage_status"], "cached")
                self.assertFalse(rows[0]["enabled"])
                self.assertNotIn("authenticated", rows[0])
                self.assertNotIn("Login expired", output)

    def test_invalid_usage_never_discovers_default_accounts(self):
        entries = [self.usage(metrics=[]), self.usage(_error="Login expired"),
                   self.usage(metrics=[{"percentage": float("nan")}]),
                   self.usage(metrics=[{"percentage": float("inf")}]),
                   self.usage(metrics=[{"percentage": 10 ** 400}]),
                   self.usage(metrics=[{"percentage": "unknown"}]),
                   self.usage(metrics=[{"detail": "Usage not available"}])]
        for entry in entries:
            with self.subTest(entry=entry):
                self.save_usage([entry])
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                self.assertEqual(json.loads(output), [])

    def test_amount_and_unlimited_usage_can_discover_a_default_connection(self):
        for metric in ({"type": "balance", "amount": 0, "currency": "USD"}, {"type": "quota", "value": "Unlimited"}):
            with self.subTest(metric=metric):
                self.save_usage([self.usage(metrics=[metric])])
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                rows = json.loads(output)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["usage_status"], "available")

    def test_saved_accounts_distinguish_unavailable_cached_and_unchecked_usage(self):
        records = [accounts.normalize({"id": identity, "provider": "codex", "enabled": False})
                   for identity in ("failed", "cached", "unchecked")]
        accounts.save_document({"version": 1, "accounts": records}, config.accounts_file())
        self.save_usage([self.usage("account:failed", metrics=[], _error="Login expired"),
                         self.usage("account:cached", _cached=True, _error="Login expired")])
        result, output, errors = self.invoke(["accounts", "--json"])
        self.assertEqual((result, errors), (0, ""))
        rows = json.loads(output)
        self.assertEqual({row["id"]: row["usage_status"] for row in rows},
                         {"failed": "unavailable", "cached": "cached", "unchecked": "not_checked"})
        self.assertTrue(all(not row["enabled"] for row in rows))

    def test_saved_usage_cannot_survive_a_provider_edit_or_another_account_identity(self):
        record = accounts.normalize({"id": "work", "provider": "codex"})
        accounts.save_document({"version": 1, "accounts": [record]}, config.accounts_file())
        self.save_usage([self.usage("account:work", _account_id="work")])
        update = self.root / "provider-update.json"
        update.write_text('{"provider":"openrouter"}', encoding="utf-8")
        with patch.object(state, "trigger_refresh"):
            result, output, errors = self.invoke(["accounts", "edit", "work", "--file", str(update)])
        self.assertEqual((result, errors), (0, ""))
        without_context = self.usage("account:work")
        del without_context["_dir"]
        cases = (
            (self.usage("account:work", _account_id="work"), "not_checked"),
            (self.usage("account:work", _dir="openrouter", _account_id="other"), "not_checked"),
            (self.usage("account:work", _dir="openrouter", _account_id="work"), "available"),
            (without_context, "available"),
        )
        for entry, expected in cases:
            with self.subTest(entry=entry):
                self.save_usage([entry])
                result, output, errors = self.invoke(["accounts", "--json"])
                self.assertEqual((result, errors), (0, ""))
                rows = json.loads(output)
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0]["provider"], rows[0]["connection_id"], rows[0]["usage_status"]),
                                 ("openrouter", "account:work", expected))

    def test_saved_only_json_preserves_old_schema_and_skips_usage_discovery(self):
        record = accounts.normalize({"id": "work", "provider": "codex", "env": {"CODEX_ACCESS_TOKEN": "WORK_TOKEN"},
                                     "options": {"organization_id": "private-option-value"}})
        accounts.save_document({"version": 1, "accounts": [record]}, config.accounts_file())
        with patch.object(state, "load_cache", side_effect=AssertionError("Saved listing must not inspect usage")), \
                patch.object(cli, "_cache_age", side_effect=AssertionError("Saved listing must not inspect cache metadata")), \
                patch.object(accounts, "prepare", side_effect=AssertionError("Listing must not resolve credentials")):
            result, output, errors = self.invoke(["accounts", "--saved", "--json"])
        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(json.loads(output), [accounts.public_record(record)])
        self.assertNotIn("private-option-value", output)

    def test_accounts_refresh_explicitly_fetches_and_saves_before_listing(self):
        data = [self.usage()]
        for arguments in (["accounts", "--refresh", "--json"], ["accounts", "list", "--refresh", "--json"],
                          ["accounts", "--refresh", "list", "--json"]):
            with self.subTest(arguments=arguments):
                events = []

                def collect(**kwargs):
                    events.append("collect")
                    return data

                def publish(value):
                    events.append("publish")
                    self.save_usage(value)

                with patch.object(fetch, "fetch_all_data", side_effect=collect) as query, \
                        patch.object(state, "save_cache", side_effect=publish) as save:
                    result, output, errors = self.invoke(arguments)
                self.assertEqual((result, errors), (0, ""))
                self.assertEqual(events, ["collect", "publish"])
                query.assert_called_once_with(include_errors=True)
                save.assert_called_once_with(data)
                self.assertEqual(json.loads(output)[0]["connection_id"], "codex")

    def test_default_connections_cannot_be_edited_or_removed_as_saved_accounts(self):
        self.save_usage([self.usage()])
        before = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        for arguments in (["accounts", "remove", "default:codex"], ["accounts", "edit", "default:codex", "--disabled"]):
            with self.subTest(arguments=arguments), patch.object(state, "trigger_refresh") as refresh:
                result, output, errors = self.invoke(arguments)
                self.assertEqual((result, output), (1, ""))
                self.assertIn("ai-status config", errors)
                refresh.assert_not_called()
                after = {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
                self.assertEqual(after, before)

    def test_status_keeps_json_schema_account_identity_and_cache(self):
        data = [{"_dir": "openrouter", "_connection_id": "account:work", "_idx": 0,
                 "provider": "OpenRouter — Trabalho", "metrics": [
                     {"type": "balance", "amount": 75, "currency": "USD"}]}]

        def collect(*args, **kwargs):
            kwargs["on_error"]("account:personal", "Credentials expired")
            return data

        with patch.object(fetch, "fetch_all_data", side_effect=collect) as query, \
                patch.object(state, "save_cache") as save:
            result, output, errors = self.invoke(["status"])
        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(json.loads(output), {"providers": data, "errors": {"account:personal": "Credentials expired"}})
        query.assert_called_once()
        save.assert_called_once_with(data)

    def test_doctor_keeps_json_diagnostics_without_collecting_usage_or_http(self):
        tray = types.ModuleType("core.tray")
        tray.status_icon = Mock(return_value=Mock(isNull=Mock(return_value=False)))
        tray.smoke_test = Mock()
        widgets = types.ModuleType("PySide6.QtWidgets")
        widgets.QApplication = Mock()
        with patch.dict(sys.modules, {"core.tray": tray, "PySide6.QtWidgets": widgets}), \
                patch.object(core, "tray", tray, create=True), \
                patch.object(fetch, "get_version_info", return_value={"current": "1.2.3"}), \
                patch.object(config, "available_providers", return_value=["codex", "openrouter"]), \
                patch.object(fetch, "fetch_all_data") as query, patch.object(provider_http, "request") as request, \
                patch.object(paths, "IS_WINDOWS", False):
            result, output, errors = self.invoke(["doctor"])
        self.assertEqual((result, errors), (0, ""))
        info = json.loads(output)
        self.assertEqual(info["version"], "1.2.3")
        self.assertEqual(info["providers"], ["codex", "openrouter"])
        self.assertEqual(info["config"], str(self.root / "config"))
        self.assertEqual(info["cache"], str(self.root / "cache"))
        self.assertIsInstance(info["desktop"], bool)
        self.assertIsInstance(info["conpty"], bool)
        tray.smoke_test.assert_not_called()
        query.assert_not_called()
        request.assert_not_called()

    def test_doctor_private_smoke_flags_keep_packaged_json_contract(self):
        tray = types.ModuleType("core.tray")
        tray.status_icon = Mock(return_value=Mock(isNull=Mock(return_value=False)))
        smoke = {"widget_render": True, "provider_icons": True, "native_console": True}
        tray.smoke_test = Mock(return_value=smoke)
        widgets = types.ModuleType("PySide6.QtWidgets")
        widgets.QApplication = Mock()
        console = types.ModuleType("core.windows_console")
        console.available = Mock(return_value=True)
        with patch.dict(sys.modules, {"core.tray": tray, "PySide6.QtWidgets": widgets, "core.windows_console": console}), \
                patch.object(core, "tray", tray, create=True), patch.object(core, "windows_console", console, create=True), \
                patch.object(paths, "IS_WINDOWS", True), patch.object(fetch, "fetch_all_data") as query, \
                patch.object(provider_http, "request", return_value='{"current_user_url":"mock-user"}') as request:
            result, output, errors = self.invoke(["doctor", "--smoke", "--http-smoke"])
        self.assertEqual((result, errors), (0, ""))
        info = json.loads(output)
        for key, value in smoke.items():
            self.assertEqual(info[key], value)
        self.assertTrue(info["desktop"])
        self.assertTrue(info["conpty"])
        self.assertTrue(info["native_https"])
        tray.smoke_test.assert_called_once_with()
        request.assert_called_once_with("https://api.github.com/", timeout=10)
        query.assert_not_called()

    def test_doctor_https_smoke_records_server_replies_without_querying_accounts(self):
        for status in (403, 429, 503):
            with self.subTest(status=status), \
                    patch.object(paths, "IS_WINDOWS", True), \
                    patch.object(fetch, "fetch_all_data") as query, \
                    patch.object(provider_http, "request", side_effect=provider_http.QueryError("Server reply", status=status)):
                result, output, errors = self.invoke(["doctor", "--http-smoke"])
                self.assertEqual((result, errors), (0, ""))
                info = json.loads(output)
                self.assertTrue(info["native_https"])
                self.assertEqual(info["native_https_http_status"], status)
                query.assert_not_called()

    def test_doctor_https_smoke_keeps_transport_and_certificate_failures_fatal(self):
        for message in ("Usage API unreachable; check your connection.", "TLS certificate validation failed"):
            error = provider_http.QueryError(message)
            with self.subTest(message=message), \
                    patch.object(paths, "IS_WINDOWS", True), \
                    patch.object(provider_http, "request", side_effect=error), \
                    self.assertRaises(provider_http.QueryError) as caught:
                self.invoke(["doctor", "--http-smoke"])
            self.assertIs(caught.exception, error)

    def test_providers_lists_installed_ids_and_enable_state_without_collecting(self):
        with patch.object(config, "available_providers", return_value=["codex", "openrouter"]), \
                patch.object(config, "enabled_order", return_value=["codex"]), \
                patch.object(fetch, "fetch_all_data") as query, patch.object(provider_http, "request") as request:
            result, output, errors = self.invoke(["providers"])
            json_result, json_output, json_errors = self.invoke(["providers", "--json"])
        self.assertEqual((result, errors, json_result, json_errors), (0, "", 0, ""))
        for detail in ("ID", "NAME", "DEFAULT CONNECTION", "codex", "openrouter", "enabled", "disabled"):
            self.assertIn(detail, output)
        info = json.loads(json_output)
        self.assertIsInstance(info, list)
        self.assertEqual({item["id"] for item in info}, {"codex", "openrouter"})
        self.assertEqual({item["id"]: item["enabled"] for item in info}, {"codex": True, "openrouter": False})
        query.assert_not_called()
        request.assert_not_called()

    def test_provider_names_use_metadata_bundled_with_windows_package(self):
        library = self.root / "packaged/lib"
        (library / "assets").mkdir(parents=True)
        (library / "assets/providers.json").write_text(
            json.dumps({"codex": {"name": "Bundled Codex Name"}}), encoding="utf-8",
        )
        with patch.object(paths, "LIB_DIR", library), \
                patch.object(config, "available_providers", return_value=["codex"]), \
                patch.object(config, "enabled_order", return_value=["codex"]):
            result, output, errors = self.invoke(["providers", "--json"])
        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(json.loads(output), [{"id": "codex", "name": "Bundled Codex Name", "enabled": True}])

    def test_daemon_format_accepts_legacy_options_before_and_after_command(self):
        for arguments, expected in ((["daemon"], "waybar"),
                                    (["daemon", "--format", "quickshell"], "quickshell"),
                                    (["--format", "quickshell", "daemon"], "quickshell"),
                                    (["daemon", "--format", "macos"], "macos")):
            with self.subTest(arguments=arguments), patch.object(daemon, "run") as run, \
                    patch("builtins.open", return_value=io.StringIO()):
                result, output, errors = self.invoke(arguments)
                self.assertEqual((result, output, errors), (0, "", ""))
                run.assert_called_once_with(output_format=expected)

    def test_frontend_actions_accept_legacy_option_positions(self):
        for command, function in (("scroll-up", "scroll_up"), ("scroll-down", "scroll_down"), ("cycle-metric", "cycle_metric")):
            for arguments in ([command, "--frontend", "macos"], ["--frontend", "macos", command]):
                with self.subTest(arguments=arguments), patch.object(cli, function) as action:
                    result, output, errors = self.invoke(arguments)
                    self.assertEqual((result, output, errors), (0, "", ""))
                    action.assert_called_once_with("macos")

    def test_native_json_actions_preserve_legacy_option_positions_and_payloads(self):
        selection = {"provider": "account:work", "idx": 0, "metric": "balance"}
        settings = {"enabled": ["account:work"], "selected": selection, "iconMode": "logo"}
        for command, option, payload, function in (("select-metric", "--selection-json", selection, "select_metric"),
                                                   ("save-settings", "--settings-json", settings, "save_settings")):
            flags = ["--frontend", "macos", option, json.dumps(payload)]
            for arguments in ([command, *flags], [*flags, command]):
                with self.subTest(arguments=arguments), patch.object(cli.quickshell, function) as action:
                    result, output, errors = self.invoke(arguments)
                self.assertEqual((result, output, errors), (0, "", ""))
                action.assert_called_once_with(payload)

    def test_private_query_preserves_collector_json(self):
        payload = {"_ai_status_error": "Log in with your provider CLI"}
        with patch.object(fetch, "run_query", side_effect=lambda provider: print(json.dumps(payload))) as query:
            result, output, errors = self.invoke(["--query", "codex"])
        self.assertEqual((result, errors), (0, ""))
        self.assertEqual(json.loads(output), payload)
        query.assert_called_once_with("codex")

    def test_no_arguments_and_config_keep_native_desktop_launches(self):
        for platform, windows in (("win32", True), ("darwin", False)):
            for arguments, configured in (([], False), (["config"], True)):
                with self.subTest(platform=platform, arguments=arguments):
                    tray = types.ModuleType("core.tray")
                    tray.run = Mock()
                    with patch.object(sys, "platform", platform), patch.object(paths, "IS_WINDOWS", windows), \
                            patch.dict(sys.modules, {"core.tray": tray}), \
                            patch.object(core, "tray", tray, create=True), patch.object(macos, "launch") as launch:
                        result, output, errors = self.invoke(arguments)
                    self.assertEqual((result, output, errors), (0, "", ""))
                    if windows:
                        tray.run.assert_called_once_with(configure=configured)
                        launch.assert_not_called()
                    else:
                        launch.assert_called_once_with(configure=configured)
                        tray.run.assert_not_called()

    def test_macos_explicit_frontend_config_opens_tui_instead_of_native_settings(self):
        for platform, windows in (("darwin", False), ("linux", False)):
            for arguments in (["config", "--frontend", "quickshell"], ["--frontend", "quickshell", "config"]):
                with self.subTest(platform=platform, arguments=arguments):
                    tray = types.ModuleType("core.tray")
                    tray.run = Mock()
                    tui = types.ModuleType("core.tui")
                    tui.run = Mock()
                    with patch.object(sys, "platform", platform), patch.object(paths, "IS_WINDOWS", windows), \
                            patch.dict(sys.modules, {"core.tray": tray, "core.tui": tui}), \
                            patch.object(core, "tray", tray, create=True), patch.object(core, "tui", tui, create=True), \
                            patch.object(macos, "launch") as launch:
                        result, output, errors = self.invoke(arguments, tty=True)
                    self.assertEqual((result, output, errors), (0, "", ""))
                    tui.run.assert_called_once_with()
                    tray.run.assert_not_called()
                    launch.assert_not_called()

    def test_windows_config_with_frontend_keeps_native_settings(self):
        for arguments in (["config", "--frontend", "quickshell"], ["--frontend", "quickshell", "config"]):
            with self.subTest(arguments=arguments):
                tray = types.ModuleType("core.tray")
                tray.run = Mock()
                tui = types.ModuleType("core.tui")
                tui.run = Mock()
                with patch.object(sys, "platform", "win32"), patch.object(paths, "IS_WINDOWS", True), \
                        patch.dict(sys.modules, {"core.tray": tray, "core.tui": tui}), \
                        patch.object(core, "tray", tray, create=True), patch.object(core, "tui", tui, create=True):
                    result, output, errors = self.invoke(arguments, tty=True)
                self.assertEqual((result, output, errors), (0, "", ""))
                tray.run.assert_called_once_with(configure=True)
                tui.run.assert_not_called()

    def test_non_interactive_config_without_terminal_reports_actionable_error(self):
        with patch.object(sys, "platform", "linux"), patch.object(paths, "IS_WINDOWS", False), \
                patch("shutil.which", return_value=None), patch.object(cli.subprocess, "Popen") as launch, \
                patch.object(config, "save_config") as save_config, patch.object(state, "save_selected") as save_selection:
            result, output, errors = self.invoke(["config"])
        self.assertEqual((result, output), (1, ""))
        self.assertIn("interactive terminal", errors.lower())
        self.assertIn("ai-status config", errors)
        launch.assert_not_called()
        save_config.assert_not_called()
        save_selection.assert_not_called()

    def test_non_interactive_macos_config_propagates_frontend_to_terminal(self):
        def terminal(name):
            return "/usr/bin/kitty" if name == "kitty" else None

        with patch.object(sys, "platform", "darwin"), patch.object(paths, "IS_WINDOWS", False), \
                patch.object(sys, "argv", [str(ENTRYPOINT)]), patch("shutil.which", side_effect=terminal), \
                patch.object(cli.subprocess, "Popen") as launch, patch.object(macos, "launch") as native:
            result, output, errors = self.invoke(["config", "--frontend", "quickshell"])
        self.assertEqual((result, output, errors), (0, "", ""))
        launch.assert_called_once_with(["/usr/bin/kitty", "-e", sys.executable, str(ENTRYPOINT.resolve()),
                                       "config", "--frontend", "quickshell"])
        native.assert_not_called()


@unittest.skipIf(sys.platform == "win32", "The terminal configuration UI uses curses")
class TerminalConfigTests(unittest.TestCase):
    def run_config(self, keys, selected, height=24, items=None):
        from core import tui
        screen = Mock()
        screen.getmaxyx.return_value = (height, 100)
        screen.getch.side_effect = keys
        items = items or [{"provider": "codex", "idx": 1, "metric": "weekly", "label": "Codex · Weekly Usage"}]
        with patch.multiple(tui.curses, initscr=Mock(return_value=screen), noecho=Mock(), cbreak=Mock(),
                            curs_set=Mock(), nocbreak=Mock(), echo=Mock(), endwin=Mock()), \
                patch.object(config, "available_connections", return_value=["codex", "claude"]), \
                patch.object(config, "enabled_connection_order", return_value=["codex", "claude"]), \
                patch.object(tui, "get_selectable_items", return_value=items), \
                patch.object(state, "load_selected", return_value=selected), \
                patch.object(state, "save_selected") as save, \
                patch.object(config, "save_connection_order") as order, \
                patch.object(state, "trigger_refresh") as refresh:
            tui.run()
        return screen, save, order, refresh

    def test_bar_checklist_appends_metrics_in_selection_order(self):
        items = [dict(provider="codex", idx=1, metric="weekly", label="Codex · Weekly"),
                 dict(provider="claude", idx=0, metric="rolling", label="Claude · Rolling")]
        initial = dict(provider="codex", idx=1, metric="weekly", icon_mode="off")
        screen, save, order, refresh = self.run_config(
            [ord(" "), ord("j"), ord(" "), ord("\n"), ord("\n")], initial, items=items)
        self.assertEqual(save.call_args.args[0]["items"], [{key: item[key] for key in ("provider", "idx", "metric")} for item in items])
        order.assert_not_called()
        refresh.assert_not_called()

    def test_canceling_bar_checklist_discards_draft_without_a_write(self):
        items = [dict(provider="codex", idx=1, metric="weekly", label="Codex · Weekly"),
                 dict(provider="claude", idx=0, metric="rolling", label="Claude · Rolling")]
        initial = dict(provider="codex", idx=1, metric="weekly")
        screen, save, order, refresh = self.run_config(
            [ord(" "), ord("j"), ord(" "), 27, ord("\n")], initial, items=items)
        save.assert_not_called()
        order.assert_not_called()
        refresh.assert_not_called()

    def test_usage_display_saves_remaining_and_preserves_other_preferences(self):
        initial = {"provider": "codex", "idx": 1, "metric": "weekly", "icon_mode": "off",
                   "custom": {"preserve": True}}
        screen, save, order, refresh = self.run_config([ord("j")] * 6 + [ord(" "), ord("\n")], initial)
        selected = save.call_args.args[0]
        self.assertEqual(selected["usage_display"], "remaining")
        for key, value in initial.items():
            self.assertEqual(selected[key], value)
        self.assertTrue(any("Usage display: < Remaining >" in call.args[2] for call in screen.addstr.call_args_list))
        order.assert_not_called()
        refresh.assert_not_called()

    def test_usage_display_can_be_changed_back_with_arrow_keys(self):
        from core import tui
        for key in (tui.curses.KEY_LEFT, tui.curses.KEY_RIGHT):
            with self.subTest(key=key):
                screen, save, order, refresh = self.run_config([ord("j")] * 6 + [key, ord("\n")],
                                                               {"usage_display": "remaining"})
                self.assertEqual(save.call_args.args[0]["usage_display"], "used")
                refresh.assert_not_called()

    def test_cancel_discards_a_usage_display_change(self):
        for cancel in (27, ord("q")):
            with self.subTest(cancel=cancel):
                screen, save, order, refresh = self.run_config([ord("j")] * 6 + [ord(" "), cancel], {})
                save.assert_not_called()
                order.assert_not_called()
                refresh.assert_not_called()

    def test_provider_navigation_and_reordering_after_display_options(self):
        screen, save, order, refresh = self.run_config([ord("j")] * 8 + [ord("J"), ord(" "), ord("\n")],
                                                       {"usage_display": "remaining"}, height=16)
        order.assert_called_once_with(["claude"])
        refresh.assert_called_once_with()
        self.assertEqual(save.call_args.args[0]["usage_display"], "remaining")


if __name__ == "__main__":
    unittest.main()
