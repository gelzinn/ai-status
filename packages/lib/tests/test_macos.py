"""macOS uses the shared native model without network logo or Waybar effects."""

import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import accounts, cli, config, daemon, fetch, macos, paths, quickshell, state, usage_credits


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
        save.assert_called_once_with({**SELECTED, **choice, "items": [choice]})
        refresh.assert_not_called()

    def test_metric_selection_keeps_other_menu_bar_items_in_provider_order(self):
        pinned = [{"provider": "claude", "idx": 0, "metric": "rolling"},
                  {"provider": "claude", "idx": 0, "metric": "weekly"}]
        choice = {"provider": "codex", "idx": 1, "metric": "weekly"}
        selected = dict(SELECTED, items=pinned)
        with patch.object(state, "load_cache", return_value=DATA), \
                patch.object(state, "load_selected", return_value=selected), \
                patch.object(state, "save_selected") as save, \
                patch.object(state, "trigger_refresh") as refresh:
            result, errors = self.invoke(["select-metric", "--frontend", "macos",
                                          "--selection-json", json.dumps(choice)])
        self.assertIn(result, (0, None), errors)
        save.assert_called_once_with({**SELECTED, **pinned[1], "items": [pinned[1], choice]})
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
            "iconMode": "bot", "usageDisplay": "remaining",
            "selected": {"provider": "codex", "idx": 1, "metric": "weekly"}}
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
        self.assertEqual(saved_selection["usage_display"], "remaining")
        self.assertFalse(saved_selection["show_provider"])
        refresh.assert_called_once_with()
        with patch.object(quickshell, "save_settings", side_effect=OSError("Permission denied")):
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json", json.dumps(payload)])
        self.assertEqual(result, 1)
        self.assertIn("Permission denied", errors)

    def test_remaining_usage_is_shared_by_native_settings_and_metrics(self):
        snapshot = quickshell.build_snapshot(DATA, dict(SELECTED, usage_display="remaining"))
        self.assertEqual(snapshot["settings"]["usageDisplay"], "remaining")
        self.assertEqual(snapshot["text"], "Claude (Pro) 100%")
        metrics = snapshot["providers"][0]["metrics"]
        self.assertEqual(metrics[0]["name"], "Rolling Remaining")
        self.assertEqual(metrics[0]["percentage"], 100)
        self.assertEqual(metrics[0]["value"], "100%")
        self.assertEqual(metrics[1]["percentage"], 38)
        self.assertEqual(quickshell.build_snapshot(DATA, SELECTED)["settings"]["usageDisplay"], "used")

    def test_invalid_usage_display_does_not_save_native_settings(self):
        payload = {"enabled": ["claude", "codex"], "display": {
            "show_provider": True, "show_model": True, "show_metric": False, "show_pct": True},
            "iconMode": "bot", "usageDisplay": "invalid",
            "selected": {"provider": "claude", "idx": 0, "metric": "rolling"}}
        with patch.object(config, "available_providers", return_value=["claude", "codex"]), \
                patch.object(state, "_save_json") as save, patch.object(state, "trigger_refresh") as refresh:
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json", json.dumps(payload)])
        self.assertEqual(result, 1)
        self.assertTrue(errors.strip())
        save.assert_not_called()
        refresh.assert_not_called()

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

    def test_cloud_credit_only_snapshots_preserve_zero_and_unavailable_states(self):
        selected = dict(SELECTED, metric="credits:claude-cloud")
        for balance, available, expires, overrides, value in (
                (75.25, True, "2099-11-05T07:59:00Z", {}, "$75.25"),
                (0, True, "2099-11-05T07:59:00Z", {}, "$0.00"),
                (75.25, True, "2000-11-05T07:59:00Z", {}, "Expired"),
                (75.25, False, "2099-11-05T07:59:00Z", {}, "Unavailable"),
                (75.25, True, "2099-11-05T07:59:00Z", {"_cached": True, "_error": "Offline"}, "Unavailable"),
                (75.25, True, "2099-11-05T07:59:00Z", {"_observed_at": time.time() - 601}, "Unavailable")):
            with self.subTest(balance=balance, value=value, overrides=overrides):
                entry = {"_dir": "claude", "_idx": 0, "provider": "Claude (Max)", "metrics": [],
                         "_observed_at": time.time(), "reset_credits": {"available": 1},
                         "monetary_credits": [{"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                             "balance": balance, "limit": 100, "used": 100 - balance,
                             "expires_at": expires, "available": available}], **overrides}
                snapshot = quickshell.build_snapshot([entry], selected)
                self.assertEqual(len(snapshot["providers"]), 1)
                provider = snapshot["providers"][0]
                self.assertEqual(provider["resetCredits"]["available"], 1)
                self.assertEqual(len(provider["monetaryCredits"]), 1)
                credit = provider["monetaryCredits"][0]
                self.assertEqual(credit["id"], "claude-cloud")
                self.assertEqual(credit["heading"], "Claude (Max) · Cloud credits")
                self.assertEqual(credit["value"], value)
                self.assertEqual(credit["observed_value"], f"${balance:.2f}")
                self.assertEqual(credit["limit_value"], "$100.00")
                self.assertEqual(credit["used_value"], f"${100 - balance:.2f}")
                self.assertIn(expires[:4], credit["expires"])
                self.assertNotIn("T07:59", credit["expires"])
                self.assertRegex(credit["timezone"], r"^UTC[+-]\d{2}:\d{2}$")
                self.assertTrue(credit["observed"])
                if value == "Expired":
                    self.assertEqual(credit["remaining"], "Expired")
                metric = provider["metrics"][0]
                self.assertEqual(metric["key"], "credits:claude-cloud")
                self.assertEqual(metric["value"], value)
                self.assertIsNone(metric["percentage"])
                self.assertFalse(metric["hasPercentage"])
                self.assertIn(expires, metric["detail"])
                self.assertEqual(snapshot["selected"]["metric"], "credits:claude-cloud")
                self.assertIn(value, snapshot["text"])
                if value in ("Expired", "Unavailable"):
                    self.assertIsNone(metric["amount"])
                    self.assertIn("Last observed $75.25", metric["detail"])

    def test_cloud_selection_preserves_account_identity_and_quota_and_reset_credits(self):
        accounts.save_document({"version": 1, "accounts": [
            {"id": "cloud-work", "provider": "claude", "label": "Work"},
            {"id": "cloud-personal", "provider": "claude", "label": "Personal"},
        ]}, config.accounts_file())
        data = [dict(_dir="claude", _connection_id="account:cloud-" + identity,
                     _account_label=label, _idx=0, provider="Claude (Max)", _observed_at=time.time(),
                     reset_credits={"available": 1}, metrics=[{"type": "rolling", "percentage": 9}],
                     monetary_credits=[{"id": "claude-cloud", "title": "Cloud credits", "currency": "USD",
                                       "balance": balance, "expires_at": "2099-11-05T07:59:00Z", "available": True}])
                for identity, label, balance in (("work", "Work", 75.25), ("personal", "Personal", 8.5))]
        selected = dict(SELECTED, provider="account:cloud-work", metric="credits:claude-cloud")
        with patch.object(config, "enabled_order", return_value=[]), \
                patch.object(state, "load_cache", return_value=data), \
                patch.object(state, "load_selected", return_value=SELECTED.copy()), \
                patch.object(state, "save_selected") as save:
            result, errors = self.invoke(["select-metric", "--frontend", "macos",
                                          "--selection-json", json.dumps(selected)])
            snapshot = quickshell.build_snapshot(data, selected)
        self.assertIn(result, (0, None), errors)
        identity = {key: selected[key] for key in ("provider", "idx", "metric")}
        save.assert_called_once_with({**selected, "items": [identity]})
        self.assertEqual(snapshot["selected"]["provider"], "account:cloud-work")
        self.assertEqual(snapshot["text"], "Claude (Max) · Work $75.25")
        self.assertEqual(len(snapshot["providers"]), 2)
        for provider in snapshot["providers"]:
            self.assertEqual([metric["key"] for metric in provider["metrics"]], ["rolling", "credits:claude-cloud"])
            self.assertEqual(provider["resetCredits"]["available"], 1)
        self.assertEqual([(provider["id"], provider["monetaryCredits"][0]["value"], provider["monetaryCredits"][0]["heading"])
                          for provider in snapshot["providers"]],
                         [("account:cloud-work", "$75.25", "Claude (Max) · Cloud credits · Work"),
                          ("account:cloud-personal", "$8.50", "Claude (Max) · Cloud credits · Personal")])

    def test_cloud_details_report_missing_fields_without_inventing_values(self):
        entry = {"_dir": "claude", "_idx": 3, "provider": "Claude (Max)", "metrics": [],
                 "_observed_at": time.time(), "monetary_credits": [
                     {"id": "claude-cloud", "title": "Cloud credits", "currency": "USD", "balance": 8.5}]}
        snapshot = quickshell.build_snapshot([entry], dict(SELECTED, idx=3, metric="credits:claude-cloud"))
        provider = snapshot["providers"][0]
        self.assertEqual((provider["id"], provider["idx"]), ("claude", 3))
        credit = provider["monetaryCredits"][0]
        self.assertEqual(credit["value"], "$8.50")
        for field in ("limit_value", "used_value", "expires"):
            self.assertEqual(credit[field], "Not reported")
        self.assertEqual(credit["remaining"], "")
        self.assertEqual(credit["timezone"], "")

    def test_native_cloud_details_follow_offline_expiration_and_staleness(self):
        now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)

        class Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return now.astimezone(tz) if tz else now

        entry = {"_dir": "claude", "_idx": 0, "provider": "Claude (Max)",
                 "metrics": [{"type": "rolling", "percentage": 9}],
                 "_observed_at": now.timestamp(), "monetary_credits": [
                     {"id": "claude-cloud", "title": "Cloud credits", "currency": "USD", "balance": 42.5,
                      "limit": 100, "used": 57.5, "expires_at": (now + timedelta(seconds=2)).isoformat()}]}
        selected = dict(SELECTED, metric="rolling")
        with patch.object(usage_credits, "datetime", Clock):
            available = quickshell.build_snapshot([entry], selected)
            now += timedelta(seconds=3)
            expired = quickshell.build_snapshot([entry], selected)
            entry["monetary_credits"][0]["expires_at"] = (now + timedelta(days=2)).isoformat()
            now += timedelta(seconds=601)
            stale = quickshell.build_snapshot([entry], selected)
        for snapshot, status, value in ((available, "available", "$42.50"),
                                        (expired, "expired", "Expired"),
                                        (stale, "unavailable", "Unavailable")):
            self.assertEqual(snapshot["selected"]["metric"], "rolling")
            credit = snapshot["providers"][0]["monetaryCredits"][0]
            self.assertEqual((credit["status"], credit["value"]), (status, value))
            self.assertEqual(credit["observed_value"], "$42.50")
        self.assertEqual(expired["providers"][0]["monetaryCredits"][0]["remaining"], "Expired")
        self.assertEqual(stale["providers"][0]["monetaryCredits"][0]["status_note"], "Observation is stale")

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

    def test_macos_daemon_streams_all_ordered_menu_bar_items_with_local_logos(self):
        pinned = [{"provider": "codex", "idx": 1, "metric": "weekly"},
                  {"provider": "claude", "idx": 0, "metric": "rolling"},
                  {"provider": "claude", "idx": 0, "metric": "weekly:<b>Fable</b>"}]
        snapshots = self.daemon_snapshots(DATA, dict(SELECTED, **pinned[0], items=pinned))
        for snapshot in snapshots:
            self.assertEqual(snapshot["settings"]["items"], pinned)
            self.assertEqual([{key: item[key] for key in ("provider", "idx", "metric")}
                              for item in snapshot["barItems"]], pinned)
            self.assertTrue(snapshot["barItems"][0]["logoPath"].endswith("codex.png"))
            self.assertTrue(all(item["logoPath"].endswith("claude.png") for item in snapshot["barItems"][1:]))
        self.assertTrue(all(item["loading"] for item in snapshots[0]["barItems"]))
        self.assertEqual([item["text"] for item in snapshots[-1]["barItems"]],
                         ["Codex 40%", "Claude (Pro) 0%", "Claude (Pro) 62%"])
        self.assertFalse(any(item["loading"] for item in snapshots[-1]["barItems"]))

    def test_native_settings_save_many_menu_bar_items_and_reject_empty_lists(self):
        items = [{"provider": "claude", "idx": 0, "metric": f"weekly:model-{index}"} for index in range(24)]
        payload = {"enabled": ["claude", "codex"], "display": {
            "show_provider": True, "show_model": True, "show_metric": False, "show_pct": True},
            "iconMode": "logo", "usageDisplay": "used", "items": items, "selected": items[0]}
        with patch.object(config, "available_providers", return_value=["claude", "codex"]), \
                patch.object(state, "load_selected", return_value=SELECTED.copy()), \
                patch.object(state, "_save_json") as save, patch.object(state, "trigger_refresh") as refresh:
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json", json.dumps(payload)])
            self.assertIn(result, (0, None), errors)
            saved = save.call_args.args[1]
            self.assertEqual(saved["items"], items)
            self.assertEqual({key: saved[key] for key in ("provider", "idx", "metric")}, items[0])
            self.assertEqual(saved["icon_mode"], "logo")
            save.reset_mock()
            refresh.reset_mock()
            result, errors = self.invoke(["save-settings", "--frontend", "macos", "--settings-json",
                                          json.dumps(dict(payload, items=[]))])
            self.assertEqual(result, 1)
            self.assertTrue(errors.strip())
            save.assert_not_called()
            refresh.assert_not_called()

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
