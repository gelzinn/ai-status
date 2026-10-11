"""macOS uses the shared native model without network logo or Waybar effects."""

import contextlib
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import accounts, cli, config, daemon, fetch, macos, paths, quickshell, state


DATA = [
    {"_dir": "claude", "_idx": 0, "provider": "Claude (Pro)", "metrics": [
        {"type": "rolling", "percentage": 0, "reset_in_seconds": 3600},
        {"type": "weekly", "percentage": 62, "detail": "<b>Fable</b> · resets tomorrow"},
    ]},
    {"_dir": "codex", "_idx": 1, "provider": "Codex", "_cached": True,
     "_error": "<span>Temporarily unavailable</span>", "metrics": [
         {"type": "weekly", "percentage": 40, "reset_in_seconds": 7200},
     ]},
]
SELECTED = {"provider": "claude", "idx": 0, "metric": "rolling", "icon_mode": "logo",
            "show_provider": True, "show_model": True, "show_metric": False, "show_pct": True}


class MacOSFrontendTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="macos connections ")
        self.addCleanup(temporary.cleanup)
        configuration = patch.object(config, "CONFIG_FILE", str(Path(temporary.name) / "providers.json"))
        configuration.start()
        self.addCleanup(configuration.stop)
        enabled = patch.object(config, "enabled_order", return_value=["claude", "codex"])
        enabled.start()
        self.addCleanup(enabled.stop)

    def invoke(self, arguments):
        errors = io.StringIO()
        with patch.object(sys, "argv", ["ai-status", *arguments]), contextlib.redirect_stderr(errors):
            result = cli.main()
        return result, errors.getvalue()

    def test_daemon_dispatches_the_macos_format(self):
        with patch.object(daemon, "run") as run:
            result, errors = self.invoke(["daemon", "--format", "macos"])
        self.assertIn(result, (0, None), errors)
        run.assert_called_once_with(output_format="macos")

    def test_metric_selection_preserves_display_preferences_without_fetch(self):
        choice = {"provider": "codex", "idx": 1, "metric": "weekly"}
        with patch.object(state, "load_cache", return_value=DATA), \
                patch.object(state, "load_selected", return_value=SELECTED.copy()), \
                patch.object(state, "save_selected") as save, \
                patch.object(state, "trigger_refresh") as refresh:
            result, errors = self.invoke(["select-metric", "--frontend", "macos",
                                          "--selection-json", json.dumps(choice)])
        self.assertIn(result, (0, None), errors)
        save.assert_called_once_with({**SELECTED, **choice})
        refresh.assert_not_called()

    def test_bad_selections_do_not_change_the_saved_metric(self):
        invalid = [None, [], "claude", {}, {"provider": "codex", "idx": True, "metric": "weekly"},
                   {"provider": "codex", "idx": -1, "metric": "weekly"},
                   {"provider": "codex", "idx": "1", "metric": "weekly"},
                   {"provider": "codex", "idx": 1, "metric": "missing"},
                   {"provider": "missing", "idx": 1, "metric": "weekly"}]
        with patch.object(state, "load_cache", return_value=DATA), patch.object(state, "save_selected") as save:
            for choice in invalid:
                with self.subTest(selection=choice):
                    result, errors = self.invoke(["select-metric", "--frontend", "macos",
                                                  "--selection-json", json.dumps(choice)])
                    self.assertEqual(result, 1)
                    self.assertTrue(errors.strip())
            result, errors = self.invoke(["select-metric", "--frontend", "macos", "--selection-json", "{"])
            self.assertEqual(result, 1)
            self.assertTrue(errors.strip())
        save.assert_not_called()

    def test_settings_use_shared_validation_and_report_write_errors(self):
        payload = {"enabled": ["codex", "claude"], "display": {
            "show_provider": False, "show_model": True, "show_metric": True, "show_pct": True},
            "iconMode": "bot", "selected": {"provider": "codex", "idx": 1, "metric": "weekly"}}
        with patch.object(config, "available_providers", return_value=["claude", "codex"]), \
                patch.object(state, "load_selected", return_value=SELECTED.copy()), \
                patch.object(state, "_save_json") as save, patch.object(state, "trigger_refresh") as refresh:
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json", json.dumps(payload)])
        self.assertIn(result, (0, None), errors)
        self.assertEqual(config.load_config(), ["codex", "claude"])
        self.assertEqual(save.call_count, 1)
        saved_selection = save.call_args.args[1]
        self.assertEqual(saved_selection["idx"], 1)
        self.assertEqual(saved_selection["icon_mode"], "bot")
        self.assertFalse(saved_selection["show_provider"])
        refresh.assert_called_once_with()
        with patch.object(quickshell, "save_settings", side_effect=OSError("Permission denied")):
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json", json.dumps(payload)])
        self.assertEqual(result, 1)
        self.assertIn("Permission denied", errors)

    def test_failed_and_nonfinite_metrics_stay_out_of_the_native_model(self):
        invalid = [
            {"_dir": "claude", "_idx": 2, "metrics": [{"type": "rolling", "percentage": float("nan")}]},
            {"_dir": "claude", "_idx": 3, "metrics": [{"type": "rolling", "percentage": float("inf")}]},
            {"_dir": "claude", "_idx": 4, "metrics": [{"type": "generic", "percentage": 0, "detail": "Authentication failed"}]},
        ]
        snapshot = quickshell.build_snapshot(DATA + invalid, SELECTED)
        self.assertEqual([(p["id"], p["idx"]) for p in snapshot["providers"]], [("claude", 0), ("codex", 1)])
        self.assertEqual(snapshot["providers"][0]["metrics"][0]["percentage"], 0)
        self.assertTrue(snapshot["providers"][1]["cached"])
        self.assertEqual(snapshot["providers"][1]["error"], "Temporarily unavailable")
        self.assertNotIn("<span", json.dumps(snapshot, allow_nan=False))

    def test_missing_first_account_preserves_the_selected_account_title(self):
        snapshot = quickshell.build_snapshot(DATA[1:], dict(SELECTED, provider="codex", idx=1, metric="weekly"))
        self.assertEqual(snapshot["text"], "Codex 40%")
        self.assertEqual(snapshot["selected"]["idx"], 1)

    def test_bundled_provider_logos_are_local_pngs_and_missing_logo_is_optional(self):
        with patch.object(quickshell.urllib.request, "urlopen") as network:
            cache = macos.LogoCache()
            for name in ("claude", "codex"):
                with self.subTest(provider=name):
                    filename = Path(cache.get(name))
                    self.assertTrue(filename.is_absolute())
                    self.assertTrue(filename.is_relative_to(paths.LIB_DIR))
                    self.assertEqual(filename.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(cache.get("unavailable-provider"), "")
            self.assertEqual(cache.get("../../outside"), "")
        network.assert_not_called()

    def test_macos_daemon_streams_shared_snapshot_without_remote_logos_or_pango(self):
        snapshots = self.daemon_snapshots(DATA, SELECTED)
        self.assertEqual(snapshots[-1]["selected"]["metric"], "rolling")
        self.assertTrue(snapshots[-1]["providers"][0]["logoPath"].endswith(".png"))

    def test_macos_daemon_keeps_account_identity_loading_selection_and_local_logo(self):
        accounts.save_document({"version": 1, "accounts": [
            {"id": "work", "provider": "openrouter", "label": "Work"},
            {"id": "personal", "provider": "openrouter", "label": "Personal"},
        ]}, config.accounts_file())
        data = [dict(_dir="openrouter", _connection_id="account:" + identity,
                     _account_label=label, _idx=idx, provider="OpenRouter", metrics=[
                         dict(type="balance", percentage=None, amount=amount, unit="USD")])
                for identity, label, idx, amount in (("personal", "Personal", 0, 8.25), ("work", "Work", 1, 42.5))]
        selected = dict(SELECTED, provider="account:work", idx=1, metric="balance")
        with patch.object(config, "enabled_order", return_value=[]):
            snapshots = self.daemon_snapshots(data, selected)
            with patch.object(state, "load_cache", return_value=data), \
                    patch.object(state, "load_selected", return_value=selected), \
                    patch.object(state, "save_selected") as save:
                result, errors = self.invoke(["select-metric", "--frontend", "macos",
                                              "--selection-json", json.dumps(selected)])
            self.assertIn(result, (0, None), errors)
            save.assert_called_once_with(selected)
        self.assertTrue(all(provider["loading"] for provider in snapshots[0]["providers"]))
        snapshot = snapshots[-1]
        self.assertEqual(snapshot["text"], "OpenRouter · Work $42.50")
        self.assertEqual(snapshot["selected"]["provider"], "account:work")
        self.assertEqual(snapshot["selected"]["idx"], 1)
        self.assertTrue(snapshot["logoPath"].endswith("openrouter.png"))
        self.assertEqual(snapshot["settings"]["providerIds"]["account:work"], "openrouter")
        self.assertEqual(snapshot["settings"]["names"]["account:work"], "OpenRouter · Work")
        metric = snapshot["providers"][0]["metrics"][0]
        self.assertIsNone(metric["percentage"])
        self.assertFalse(metric["hasPercentage"])
        self.assertEqual(metric["value"], "$42.50")

    def daemon_snapshots(self, data, selected):
        class PendingThread:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

        sleep_count = 0

        def advance(seconds):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count == 1:
                daemon._pending.clear()
                daemon.is_updating = False
            else:
                raise KeyboardInterrupt

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            # Exercise the native renderer without changing this test runner's
            # process group or requiring POSIX-only APIs on Windows.
            stack.enter_context(patch.object(daemon.os, "getpgrp", return_value=-1, create=True))
            stack.enter_context(patch.object(daemon.os, "setsid", create=True))
            stack.enter_context(patch.object(state, "register_pid"))
            stack.enter_context(patch.object(state, "unregister_pid"))
            stack.enter_context(patch.object(state, "load_cache", return_value=data))
            stack.enter_context(patch.object(state, "load_selected", return_value=selected.copy()))
            stack.enter_context(patch.object(state, "save_selected"))
            stack.enter_context(patch.object(fetch, "check_for_updates"))
            network = stack.enter_context(patch.object(quickshell.urllib.request, "urlopen"))
            remote_cache = stack.enter_context(patch.object(quickshell.LogoCache, "get"))
            stack.enter_context(patch.object(daemon.threading, "Thread", PendingThread))
            stack.enter_context(patch.object(daemon.time, "sleep", side_effect=advance))
            logo = stack.enter_context(patch.object(daemon.logos, "update_current"))
            notification = stack.enter_context(patch.object(daemon.logos, "signal_waybar"))
            tooltip = stack.enter_context(patch.object(daemon.logos, "write_tooltip"))
            stack.enter_context(contextlib.redirect_stdout(output))
            daemon.run("macos")
            network.assert_not_called()
            remote_cache.assert_not_called()
            logo.assert_not_called()
            notification.assert_not_called()
            tooltip.assert_not_called()
        snapshots = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertGreaterEqual(len(snapshots), 2)
        self.assertTrue(all(snapshot["schemaVersion"] == 1 for snapshot in snapshots))
        self.assertTrue(snapshots[0]["loading"])
        self.assertFalse(snapshots[-1]["loading"])
        self.assertNotIn("<span", output.getvalue())
        self.assertNotIn("tooltip", snapshots[-1])
        return snapshots

    def test_refresh_uses_the_platform_signal_number(self):
        with tempfile.TemporaryDirectory() as directory:
            pidfile = Path(directory) / "pids"
            pidfile.write_text("123\ninvalid\n456\n")
            # Darwin uses 30 for SIGUSR1; Linux uses 10. A hard-coded Linux
            # number would send SIGBUS to the macOS process instead of refresh.
            with patch.object(paths, "IS_WINDOWS", False), patch.object(state, "PID_FILE", str(pidfile)), \
                    patch.object(signal, "SIGUSR1", 30, create=True), patch.object(state.os, "kill") as kill, \
                    patch.object(state, "fcntl", create=True):
                state.trigger_refresh()
            self.assertEqual([call.args for call in kill.call_args_list], [(123, 30), (456, 30)])


if __name__ == "__main__":
    unittest.main()
