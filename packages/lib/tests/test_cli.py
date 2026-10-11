"""Exercise CLI help, safe account listings and existing desktop contracts."""

import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

LIB = Path(__file__).resolve().parents[1]
SRC = LIB / "src"
ENTRYPOINT = SRC / "bin" / "ai-status"
sys.path.insert(0, str(SRC))
import core
from core import __version__, cli, config, daemon, fetch, macos, paths, provider_http, state


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
                self.assert_help(self.invoke(flag), "accounts", "providers", "status", "doctor", "config", "--version")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Native desktops keep their no-argument launcher")
    def test_no_arguments_on_linux_prints_help_and_exits_successfully(self):
        self.assert_help(self.invoke(), "accounts", "providers", "config")

    def test_subcommand_help_and_help_command_are_equivalent(self):
        cases = {
            "accounts": ("add", "edit", "list", "remove"),
            "providers": ("--json",),
            "status": ("status",),
            "doctor": ("doctor", "JSON"),
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
            ("daemon", "--format", "unknown-format"),
            ("refresh", "--settings-json", "{}"),
            ("status", "--format", "quickshell"), ("help", "unknown-command"),
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

    def test_accounts_without_action_explains_default_sessions_and_next_steps(self):
        result = self.invoke("accounts")
        self.assertEqual((result.returncode, result.stderr), (0, ""))
        self.assertIn("default", result.stdout.lower())
        self.assertIn("ai-status accounts add", result.stdout)
        self.assertIn("ai-status providers", result.stdout)
        for arguments in (("accounts", "--json"), ("accounts", "list", "--json")):
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
        for arguments in (("accounts",), ("accounts", "list"), ("accounts", "--json"), ("accounts", "list", "--json")):
            with self.subTest(arguments=arguments):
                result = self.invoke(*arguments)
                self.assertEqual((result.returncode, result.stderr), (0, ""))
                for secret in ("private-environment-value", "private-credential-content", "private-project-value"):
                    self.assertNotIn(secret, result.stdout + result.stderr)
                if "--json" in arguments:
                    self.assertEqual(json.loads(result.stdout), [public])
                else:
                    self.assertIn("ID", result.stdout)
                    self.assertIn("Trabalho", result.stdout)
                    self.assertIn("enabled", result.stdout.lower())


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
            (state, "CACHE_FILE", str(self.root / "usage.json")),
            (state, "SELECTED_FILE", str(self.root / "config/selected.json")),
        ):
            item = patch.object(target, name, value)
            item.start()
            self.addCleanup(item.stop)

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


if __name__ == "__main__":
    unittest.main()
