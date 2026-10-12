"""Quota alert collection and settings contracts across desktop entry points."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, config, daemon, desktop_notifications, fetch, notifications, paths, quickshell, state


def parse(name, payload):
    filename = paths.PROVIDERS_DIR / name / "parse.py"
    spec = importlib.util.spec_from_file_location("notification_parse_" + name, filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse(json.dumps(payload))


class NotificationIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        for replacement in (
            patch.object(paths, "CONFIG_DIR", self.root),
            patch.object(config, "CONFIG_FILE", str(self.root / "providers.json")),
            patch.object(config, "available_providers", return_value=["codex", "claude"]),
            patch.object(state, "SELECTED_FILE", str(self.root / "selected.json")),
            patch.object(state, "CACHE_FILE", str(self.root / "usage.json")),
            patch.object(fetch, "CACHE_DIR", str(self.root / "providers")),
            patch.object(state, "trigger_refresh"),
        ):
            stack.enter_context(replacement)
        config.save_config(["codex", "claude"])

    def invoke(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            result = cli.main(list(arguments))
        return result, output.getvalue(), errors.getvalue()

    def test_cli_global_rule_silence_and_hours_roundtrip(self):
        result, output, errors = self.invoke("notifications", "--thresholds", "95,100", "--quiet-hours", "22:00-08:00", "--mute", "60")
        self.assertEqual((result, errors), (0, ""))
        saved = json.loads(output)
        self.assertEqual(saved["thresholds"], [95, 100])
        self.assertGreater(saved["muted_until"], time.time() + 3590)
        result, output, errors = self.invoke("notifications", "--connection", "codex", "--metric", "weekly", "--thresholds", "80,100", "--resume", "--recent-only")
        self.assertEqual((result, errors), (0, ""))
        saved = json.loads(output)
        self.assertEqual(saved["rules"], [dict(connection_id="codex", metric="weekly", enabled=True, thresholds=[80, 100])])
        self.assertEqual(saved["thresholds"], [95, 100])
        self.assertEqual(saved["muted_until"], 0)
        self.assertTrue(saved["recent_only"])

    def test_invalid_cli_settings_preserve_saved_preferences(self):
        notifications.save_settings(dict(thresholds=[95]))
        before = notifications.load_settings()
        for arguments in (("--thresholds", "99.6"), ("--thresholds", "101"), ("--mute", "-1"), ("--quiet-hours", "25:00-08:00")):
            with self.subTest(arguments=arguments):
                result, output, errors = self.invoke("notifications", *arguments)
                self.assertEqual(result, 1)
                self.assertTrue(errors)
                self.assertEqual(notifications.load_settings(), before)

    def test_native_settings_preserve_alert_rules_and_validate_before_writes(self):
        alerts = notifications.validate_settings(dict(thresholds=[95], rules=[dict(connection_id="codex", metric="weekly", thresholds=[100])]))
        payload = dict(enabled=["codex"], display=dict(show_provider=True, show_model=True, show_metric=False, show_pct=True),
                       iconMode="off", usageDisplay="remaining", selected=dict(provider="codex", idx=0, metric="weekly"), notifications=alerts)
        quickshell.save_settings(payload)
        self.assertEqual(quickshell.settings_snapshot(state.load_selected())["notifications"], alerts)
        with patch.object(config, "save_connection_order") as save_providers, patch.object(state, "_save_json") as save_selected:
            with self.assertRaises(ValueError):
                quickshell.save_settings(dict(payload, notifications=dict(thresholds=[101])))
        save_providers.assert_not_called()
        save_selected.assert_not_called()

    def test_claude_and_codex_keep_precise_percentages_and_unknown_values(self):
        claude = parse("claude", {"five_hour": {"utilization": 99.6, "resets_at": "2030-01-01T12:00:00Z"}, "seven_day": {"resets_at": "2030-01-05T12:00:00Z"}})
        codex = parse("codex", {"rate_limit": {"primary_window": {"used_percent": 99.6, "limit_window_seconds": 18000, "reset_at": 1893499200},
                                              "secondary_window": {"limit_window_seconds": 604800}}})
        for entry in (claude, codex):
            self.assertEqual(entry["metrics"][0]["percentage"], 99.6)
            self.assertIsNone(entry["metrics"][1]["percentage"])
            self.assertEqual(entry["metrics"][0]["reset_at"], 1893499200)

    def test_success_metadata_stays_original_on_coalesced_cache(self):
        connection = dict(provider="codex", connection_id="codex", account_id=None, env={}, options={})
        reply = '{"rate_limit":{"primary_window":{"used_percent":95,"limit_window_seconds":18000,"reset_after_seconds":3600}}}'
        completed = type("Completed", (), dict(stdout=reply, returncode=0))()
        with patch.object(fetch.accounts, "prepare", return_value=({}, "credential-identity", ())), \
             patch.object(fetch, "_pace_service"), patch.object(fetch.subprocess, "run", return_value=completed) as run:
            fresh = fetch.run_provider(str(paths.PROVIDERS_DIR / "codex"), connection)
            cached = fetch.run_provider(str(paths.PROVIDERS_DIR / "codex"), connection)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(fresh["_observed_at"], cached["_observed_at"])
        self.assertEqual(fresh["_fingerprint"], "credential-identity")
        self.assertAlmostEqual(fresh["metrics"][0]["reset_at"] - fresh["_observed_at"], 3600)

    def test_elapsed_reset_bypasses_short_cache_and_failed_query_is_stale(self):
        connection = dict(provider="codex", connection_id="codex", account_id=None, env={}, options={})
        old = dict(provider="Codex", _observed_at=time.time() - 20, _fingerprint="fp", metrics=[dict(type="rolling", percentage=100, reset_at=time.time() - 1)])
        fetch._save_cache(str(paths.PROVIDERS_DIR / "codex"), old, connection, "fp")
        with patch.object(fetch.accounts, "prepare", return_value=({}, "fp", ())), \
             patch.object(fetch, "_pace_service"), patch.object(fetch.subprocess, "run", side_effect=OSError("offline")) as query:
            result = fetch.run_provider(str(paths.PROVIDERS_DIR / "codex"), connection)
        query.assert_called_once()
        self.assertTrue(result["_cached"])
        self.assertEqual(result["_observed_at"], old["_observed_at"])
        with patch.object(desktop_notifications, "deliver") as deliver:
            self.assertEqual(notifications.process([result], deliver), [])
        deliver.assert_not_called()

    def test_fresh_response_reporting_old_reset_keeps_request_coalescing(self):
        connection = dict(provider="codex", connection_id="codex", account_id=None, env={}, options={})
        fresh = dict(provider="Codex", _observed_at=time.time(), _fingerprint="fp", metrics=[dict(type="rolling", percentage=100, reset_at=time.time() - 5)])
        fetch._save_cache(str(paths.PROVIDERS_DIR / "codex"), fresh, connection, "fp")
        with patch.object(fetch.accounts, "prepare", return_value=({}, "fp", ())), patch.object(fetch.subprocess, "run") as query:
            result = fetch.run_provider(str(paths.PROVIDERS_DIR / "codex"), connection)
        self.assertEqual(result, fresh)
        query.assert_not_called()

    def test_daemon_evaluates_only_returned_results(self):
        fresh = dict(provider="Codex", _dir="codex", _connection_id="codex", _fingerprint="fp", _observed_at=time.time(), metrics=[dict(type="weekly", percentage=95)])
        def collect(**options):
            options["on_result"]("codex", [fresh])
            return [fresh]
        with patch.object(state, "acquire_lock", return_value=True), patch.object(state, "release_lock"), \
             patch.object(fetch, "fetch_all_data", side_effect=collect), patch.object(desktop_notifications, "deliver", return_value=True) as deliver:
            daemon.update_task("waybar")
        self.assertEqual(deliver.call_count, 1)
        self.assertEqual(deliver.call_args.args[0]["threshold"], 95)


if __name__ == "__main__":
    unittest.main()
