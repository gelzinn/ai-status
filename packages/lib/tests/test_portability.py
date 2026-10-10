import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
from core import cli, config, daemon, fetch, paths, render, state
from core.provider_http import QueryError, output, request


def load_provider(name, script="query"):
    spec = importlib.util.spec_from_file_location(f"{name}_{script}", SRC / "providers" / name / f"{script}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class IsolatedState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="AI Status é ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.patches = []
        for module, key, value in (
            (paths, "RUNTIME_DIR", self.root / "runtime"),
            (config, "CONFIG_FILE", str(self.root / "providers.json")),
            (config, "CONFIG_DIR", str(self.root)),
            (state, "CACHE_FILE", str(self.root / "usage.json")),
            (state, "SELECTED_FILE", str(self.root / "selected.json")),
            (state, "LOCK_FILE", str(self.root / "query.lock")),
            (state, "REFRESH_FILE", str(self.root / "refresh.json")),
            (fetch, "CACHE_DIR", str(self.root / "cache")),
        ):
            item = patch.object(module, key, value)
            item.start()
            self.addCleanup(item.stop)
        env = patch.dict(os.environ, {"HOME": str(self.root), "USERPROFILE": str(self.root),
                                     "XDG_DATA_HOME": str(self.root / "data"),
                                     "XDG_CONFIG_HOME": str(self.root / "config"),
                                     "CODEX_HOME": str(self.root / "codex"),
                                     "CLAUDE_CONFIG_DIR": str(self.root / "claude"),
                                     "PYTHONIOENCODING": "utf-8",
                                     "COMMANDCODE_API_KEY": ""})
        env.start()
        self.addCleanup(env.stop)

    def write(self, path, data):
        paths.atomic_json(path, data)


class PlatformTests(IsolatedState):
    def test_windows_paths_are_per_user(self):
        env = {**os.environ, "PYTHONPATH": str(SRC), "APPDATA": str(self.root / "roaming"),
               "LOCALAPPDATA": str(self.root / "local")}
        result = subprocess.run([sys.executable, "-c",
            "import sys, tempfile; sys.platform='win32'; from core import paths; "
            "print(paths.CONFIG_DIR); print(paths.RUNTIME_DIR)"], env=env,
            capture_output=True, text=True, encoding="utf-8", check=True)
        self.assertIn(str(self.root / "roaming" / "ai-status"), result.stdout)
        self.assertIn(str(self.root / "local" / "ai-status" / "cache" / "runtime"), result.stdout)

    def test_cli_import_does_not_require_curses_or_qt(self):
        result = subprocess.run([sys.executable, "-c",
            "import sys; from core import cli; "
            "assert 'curses' not in sys.modules; assert 'PySide6' not in sys.modules"],
            env={**os.environ, "PYTHONPATH": str(SRC)}, capture_output=True, check=True)
        self.assertEqual(result.returncode, 0)

    def test_lock_is_exclusive_and_recovers_stale_lock(self):
        self.assertTrue(state.acquire_lock())
        self.assertFalse(state.acquire_lock())
        os.utime(state.LOCK_FILE, (time.time() - 100, time.time() - 100))
        self.assertTrue(state.acquire_lock())
        state.release_lock()
        self.assertFalse(Path(state.LOCK_FILE).exists())

    def test_unicode_selection_roundtrip_and_empty_provider_list(self):
        selected = {"provider": "claude", "label": "Sessão · 使用"}
        state.save_selected(selected)
        self.assertEqual(state.load_selected(), selected)
        config.save_config([])
        self.assertEqual(config.enabled_order(), [])
        self.assertEqual(fetch.fetch_all_data(), [])
        self.assertFalse(list(self.root.glob("*.tmp")))

    def test_windows_refresh_never_sends_unix_signals(self):
        with patch.object(paths, "IS_WINDOWS", True), patch("os.kill") as kill:
            state.register_pid()
            state.trigger_refresh()
            first = paths.read_json(state.REFRESH_FILE)
            state.trigger_refresh()
            self.assertNotEqual(first, paths.read_json(state.REFRESH_FILE))
            kill.assert_not_called()

    def test_linux_refresh_keeps_signal_protocol(self):
        pid_file = self.root / "pids"
        pid_file.write_text("123\n", encoding="utf-8")
        # Simulate the Unix file-lock API too when this runs on Windows.
        with patch.object(paths, "IS_WINDOWS", False), patch.object(state, "PID_FILE", str(pid_file)), patch.object(state, "fcntl", create=True) as locks, patch("os.kill") as kill:
            state.trigger_refresh()
            locks.flock.assert_called_once()
            self.assertEqual(locks.flock.call_args.args[1], locks.LOCK_SH)
            kill.assert_called_once_with(123, 10)

    def test_python_scripts_use_interpreter_and_frozen_sibling(self):
        query = str(SRC / "providers/codex/query.py")
        self.assertEqual(fetch.query_command(query), [sys.executable, query])
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "executable", str(self.root / "ai-status.exe")):
            self.assertEqual(fetch.query_command(query), [str(self.root / "ai-status-cli.exe"), "--query", "codex"])

    def test_real_subprocess_supports_spaces_unicode_and_missing_auth(self):
        provider = self.root / "providers/test-provider"
        provider.mkdir(parents=True)
        (provider / "query.py").write_text("print('{\"value\": \"使用\"}')", encoding="utf-8")
        (provider / "parse.py").write_text("def parse(raw):\n return {'provider':'Test 使用','metrics':[{'percentage':42}]}\n", encoding="utf-8")
        result = fetch.run_provider(str(provider))
        self.assertEqual(result["provider"], "Test 使用")
        self.assertEqual(fetch.run_provider(str(SRC / "providers/codex"))["error"], "Sign in to Codex with your ChatGPT account.")

    def test_query_errors_and_timeout_mark_cached_data(self):
        directory = str(SRC / "providers/codex")
        fetch._save_cache(directory, {"provider": "Codex", "metrics": [{"percentage": 30}]})
        cache_path = fetch._cache_path(directory)
        cache = paths.read_json(cache_path)
        cache["timestamp"] = time.time() - fetch.MIN_REFRESH_SECONDS - 1
        self.write(cache_path, cache)
        result = fetch.run_provider(directory)
        self.assertTrue(result["_cached"])
        self.assertIn("Sign in", result["_error"])
        with patch("core.fetch.subprocess.run", side_effect=subprocess.TimeoutExpired("query", 40)):
            result = fetch.run_provider(directory)
        self.assertTrue(result["_cached"])
        self.assertIn("timed out", result["_error"])

    def test_expired_cache_does_not_hide_query_failure(self):
        directory = str(SRC / "providers/codex")
        self.write(fetch._cache_path(directory), {"timestamp": time.time() - 7200, "data": {"provider": "Codex"}})
        self.assertIn("error", fetch.run_provider(directory))

    def test_failed_provider_reports_error_and_preserves_order(self):
        config.save_config(["codex", "claude"])
        errors, results = {}, []
        def collect(directory):
            if Path(directory).name == "codex":
                return {"error": "Sign in"}
            return {"provider": "Claude", "metrics": [{"percentage": 20}]}
        with patch.object(fetch, "run_provider", side_effect=collect):
            data = fetch.fetch_all_data(on_result=lambda name, result: results.append(name),
                                       on_error=lambda name, error: errors.update({name: error}))
        self.assertEqual(errors, {"codex": "Sign in"})
        self.assertEqual(data[0]["_dir"], "claude")
        self.assertCountEqual(results, ["codex", "claude"])

    def test_copilot_metrics_have_distinct_selection_keys(self):
        parser = load_provider("copilot", "parse")
        self.assertEqual(parser.parse("{}")["metrics"], [])
        data = parser.parse('{"quota_snapshots":{"chat":{"limit":100,"remaining":60},"completions":{"limit":100,"remaining":10}}}')
        self.assertNotEqual(render.metric_key(data["metrics"][0]), render.metric_key(data["metrics"][1]))

    def test_internal_query_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            fetch.run_query("../../core/cli")

    def test_daemon_clears_usage_when_all_providers_are_disabled(self):
        config.save_config([])
        old = [{"provider": "Codex", "metrics": [{"percentage": 50}]}]
        with patch.object(daemon, "latest_data", old):
            daemon.update_task()
            self.assertEqual(daemon.latest_data, [])
        self.assertEqual(state.load_cache(), [])


class CollectorTests(IsolatedState):
    def test_codex_override_and_account_header(self):
        self.write(self.root / "codex/auth.json", {"tokens": {"access_token": "example", "account_id": "account"}})
        module = load_provider("codex")
        with patch.object(module, "request", return_value="{}") as api:
            self.assertEqual(module.query(), "{}")
        self.assertEqual(api.call_args.args[1]["ChatGPT-Account-Id"], "account")

    def test_claude_expired_token_falls_back_to_opencode(self):
        self.write(self.root / "claude/.credentials.json", {"claudeAiOauth": {"accessToken": "expired", "expiresAt": 1}})
        self.write(self.root / "data/opencode/auth.json", {"anthropic": {"access": "valid"}})
        module = load_provider("claude")
        with patch.object(module, "request", return_value='{"five_hour":{"utilization":21}}') as api:
            data = module.query()
        self.assertEqual(api.call_args.args[1]["Authorization"], "Bearer valid")
        self.assertEqual(load_provider("claude", "parse").parse(json.dumps(data))["metrics"][0]["percentage"], 21)

    def test_claude_native_credentials_and_plan(self):
        self.write(self.root / "claude/.credentials.json", {"claudeAiOauth": {"accessToken": "native", "subscriptionType": "pro"}})
        module = load_provider("claude")
        with patch.object(module, "request", return_value='{"five_hour":{"utilization":21}}'):
            self.assertEqual(module.query()["plan"], "pro")

    def test_copilot_uses_xdg_auth_store(self):
        self.write(self.root / "data/opencode/auth.json", {"github-copilot": {"access": "example"}})
        module = load_provider("copilot")
        with patch.object(module, "request", return_value="{}") as api:
            module.query()
        self.assertEqual(api.call_args.args[1]["Authorization"], "token example")

    def test_zai_account_selection(self):
        self.write(self.root / "data/opencode/account.json", {"accounts": [
            {"serviceID": "other", "credential": {"key": "wrong"}},
            {"serviceID": "zai-coding-plan", "credential": {"key": "example"}},
        ]})
        module = load_provider("zai")
        with patch.object(module, "request", return_value='{"success":true}') as api:
            module.query()
        self.assertEqual(api.call_args.args[1]["Authorization"], "Bearer example")

    def test_opencode_direct_usage_needs_no_cookie_or_workspace(self):
        self.write(self.root / "data/opencode/auth.json", {"opencode-go": {"key": "example"}})
        module = load_provider("opencode")
        response = '{"usage":{"rolling":{"percent":12.5,"resetsAt":"2099-01-01T00:00:00Z"}}}'
        with patch.object(module, "request", return_value=response) as api:
            self.assertEqual(module.query(), response)
        api.assert_called_once_with("https://opencode.ai/zen/go/v1/usage", {"Authorization": "Bearer example"})
        parsed = load_provider("opencode", "parse").parse(response)
        self.assertEqual(parsed["metrics"][0]["percentage"], 12.5)

    def test_commandcode_collects_budget_and_propagates_failure(self):
        module = load_provider("commandcode")
        with patch.dict(os.environ, {"COMMANDCODE_API_KEY": "example"}), patch.object(module, "_get", side_effect=[
            {"org": {"id": "test"}}, {"data": {"currentPeriodStart": "2026-01-01"}},
            {"credits": {"monthlyCredits": 8}}, {"totalCost": 2},
        ]):
            data = module.query()
        self.assertEqual(data["used"], 2)
        self.assertEqual(data["remaining"], 8)
        parsed = load_provider("commandcode", "parse").parse(json.dumps(data))
        self.assertIsNone(parsed["metrics"][0]["percentage"])
        self.assertEqual(parsed["metrics"][0]["amount"], 2)
        self.assertEqual(parsed["metrics"][1]["amount"], 8)

    def test_commandcode_uses_reported_window_caps_and_amount_only_monthly_spend(self):
        data = {"used": 12, "remaining": 30, "windows": {
            "fiveHour": {"used": 3.5, "cap": 14, "resetAt": 4070908800000},
            "weekly": {"used": 10.5, "cap": 35, "resetAt": 4070908800000},
        }}
        metrics = load_provider("commandcode", "parse").parse(json.dumps(data))["metrics"]
        self.assertEqual([metric["type"] for metric in metrics], ["rolling", "weekly", "monthly", "balance"])
        self.assertEqual([metric["percentage"] for metric in metrics[:2]], [25, 30])
        self.assertIsNone(metrics[2]["percentage"])
        self.assertEqual(metrics[2]["amount"], 12)
        self.assertGreater(metrics[0]["reset_in_seconds"], 0)

    def test_kiro_requires_native_cli_and_returns_usage(self):
        module = load_provider("kiro")
        with patch.object(module, "cli_path", return_value="kiro-cli.exe"), patch.object(module, "run_cli", side_effect=["{}", "Credits (20 of 100)"]):
            raw = module.query()
        self.assertEqual(load_provider("kiro", "parse").parse(raw)["metrics"][0]["percentage"], 20)

    def test_http_errors_do_not_expose_tokens(self):
        from urllib.error import HTTPError
        with patch("core.paths.IS_WINDOWS", False), patch("urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError("https://example.invalid?secret=example", 401, "token example", {}, None)
            with self.assertRaises(QueryError) as result:
                request("https://example.invalid", {"Authorization": "Bearer example"})
        self.assertNotIn("example", str(result.exception))
        self.assertIn("401", str(result.exception))

    def test_output_returns_structured_diagnostic(self):
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            output(lambda: (_ for _ in ()).throw(QueryError("Sign in first")))
        self.assertEqual(json.loads(stream.getvalue()), {"_ai_status_error": "Sign in first"})


if __name__ == "__main__":
    unittest.main()
