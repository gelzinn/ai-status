"""Refresh preferences and live scheduling use fixture state and fake clocks."""

import contextlib
import copy
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, config, daemon, notifications, quickshell, state


class RefreshIntervalTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status-refresh-interval-")
        self.addCleanup(temporary.cleanup)
        self.selected_file = Path(temporary.name) / "selected.json"
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for replacement in (
            patch.object(state, "SELECTED_FILE", str(self.selected_file)),
            patch.object(config, "CONFIG_FILE", str(Path(temporary.name) / "providers.json")),
            patch.object(config, "available_connections", return_value=["codex"]),
            patch.object(config, "enabled_connection_order", return_value=["codex"]),
            patch.object(notifications, "load_settings", side_effect=lambda: copy.deepcopy(notifications.DEFAULT_SETTINGS)),
        ):
            self.stack.enter_context(replacement)
        self.selected = dict(provider="codex", idx=0, metric="weekly", icon_mode="logo",
                             usage_display="used", show_provider=True, show_model=True,
                             show_metric=False, show_pct=True, refresh_interval_minutes=5)
        self.payload = dict(enabled=["codex"], selected=dict(provider="codex", idx=0, metric="weekly"),
                            iconMode="logo", usageDisplay="used",
                            display=dict(show_provider=True, show_model=True, show_metric=False, show_pct=True))
        state.save_selected(self.selected)

    def test_defaults_and_corrupt_preferences_never_speed_up_collection(self):
        self.assertEqual(state.get_refresh_interval_seconds(None), 300)
        invalid = (None, True, False, 0, 1, 4, 6, 61, 120, -5, 5.0, "5", [], {}, float("nan"))
        for value in invalid:
            with self.subTest(value=value):
                self.assertEqual(state.get_refresh_interval_seconds({"refresh_interval_minutes": value}), 300)
                with self.assertRaises(ValueError):
                    state.validate_refresh_interval_minutes(value)
        for minutes in range(5, 61, 5):
            self.assertEqual(state.get_refresh_interval_seconds({"refresh_interval_minutes": minutes}), minutes * 60)

    def test_interval_only_and_unchanged_saves_do_not_force_a_query(self):
        with patch.object(state, "trigger_refresh") as refresh, \
                patch.object(config, "save_connection_order") as order, \
                patch.object(notifications, "save_settings") as alerts:
            quickshell.save_settings(dict(self.payload, refreshIntervalMinutes=30))
            quickshell.save_settings(dict(self.payload, refreshIntervalMinutes=30))
        self.assertEqual(state.load_selected()["refresh_interval_minutes"], 30)
        self.assertEqual(quickshell.settings_snapshot(state.load_selected())["refreshIntervalMinutes"], 30)
        refresh.assert_not_called()
        order.assert_not_called()
        alerts.assert_not_called()

    def test_legacy_form_preserves_saved_interval_and_other_changes_still_refresh(self):
        state.save_selected(dict(self.selected, refresh_interval_minutes=45, legacy="keep"))
        payload = dict(self.payload, display=dict(self.payload["display"], show_model=False))
        with patch.object(state, "trigger_refresh") as refresh, patch.object(config, "save_connection_order"):
            quickshell.save_settings(payload)
        self.assertEqual(state.load_selected()["refresh_interval_minutes"], 45)
        self.assertEqual(state.load_selected()["legacy"], "keep")
        refresh.assert_called_once()

    def test_invalid_form_interval_cannot_write_or_refresh(self):
        before = self.selected_file.read_bytes()
        with patch.object(state, "trigger_refresh") as refresh, patch.object(config, "save_connection_order") as order:
            for value in (None, True, 0, 1, 6, 61, 5.0, "15", []):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    quickshell.save_settings(dict(self.payload, refreshIntervalMinutes=value))
                self.assertEqual(self.selected_file.read_bytes(), before)
        refresh.assert_not_called()
        order.assert_not_called()

    def test_periodic_swiftbar_obeys_saved_interval_and_fetches_missing_cache(self):
        state.save_selected(dict(self.selected, refresh_interval_minutes=30))
        with patch.object(cli, "_cache_age", return_value=900), \
                patch.object(cli, "_spawn_background_refresh") as refresh, \
                patch("core.swiftbar.render_from_state", return_value="Fixture"), contextlib.redirect_stdout(io.StringIO()):
            cli.swiftbar_render()
            refresh.assert_not_called()
            with patch.object(cli, "_cache_age", return_value=1800):
                cli.swiftbar_render()
            refresh.assert_called_once()
            with patch.object(cli, "_cache_age", return_value=None):
                cli.swiftbar_render()
            self.assertEqual(refresh.call_count, 2)


class DaemonRefreshScheduleTests(unittest.TestCase):
    def run_schedule(self, interval, until, change=None, collection_seconds=0):
        clock = {"now": 0, "revision": 1}
        selected = dict(provider="codex", idx=0, metric="weekly", refresh_interval_minutes=interval)
        starts, completions = [], []

        def collect(_format):
            starts.append(clock["now"])
            clock["now"] += collection_seconds
            completions.append(clock["now"])
            daemon.latest_data = []
            daemon._pending.clear()
            daemon.is_updating = False

        class ImmediateThread:
            def __init__(self, target, args, **kwargs):
                self.target, self.args = target, args

            def start(self):
                self.target(*self.args)

        def advance(_seconds):
            clock["now"] += 60
            if change is not None and clock["now"] >= change[0] and clock["revision"] == 1:
                selected["refresh_interval_minutes"] = change[1]
                clock["revision"] = 2
            if clock["now"] > until:
                raise KeyboardInterrupt

        with contextlib.ExitStack() as stack:
            for replacement in (
                patch.multiple(daemon, should_update=True, is_updating=False, latest_data=[], _results_by_dir={}, _pending=set()),
                patch.object(state, "load_cache", return_value=[]),
                patch.object(state, "load_selected", side_effect=lambda: selected.copy()),
                patch.object(daemon.paths, "read_json", return_value=None),
                patch.object(config, "enabled_connection_order", return_value=["codex"]),
                patch.object(daemon.os.path, "exists", return_value=True),
                patch.object(daemon.os.path, "getmtime", side_effect=lambda path: clock["revision"] if path == state.SELECTED_FILE else 1),
                patch.object(daemon.time, "time", side_effect=lambda: clock["now"]),
                patch.object(daemon.time, "sleep", side_effect=advance),
                patch.object(daemon.threading, "Thread", ImmediateThread),
                patch.object(daemon, "update_task", side_effect=collect),
                patch.object(daemon.render, "build_final_state", return_value={"text": "Fixture"}),
                patch.object(daemon.logos, "update_current"),
                patch.object(daemon.logos, "write_tooltip"),
                patch.object(daemon.logos, "signal_waybar"),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                stack.enter_context(replacement)
            daemon._run("waybar")
        return starts, completions

    def test_configured_cadence_waits_after_each_completed_collection(self):
        starts, completions = self.run_schedule(15, 1200, collection_seconds=120)
        self.assertEqual(len(starts), 2)
        self.assertGreaterEqual(starts[1] - completions[0], 900)

    def test_long_interval_does_not_keep_the_old_five_minute_cadence(self):
        starts, _ = self.run_schedule(30, 1200)
        self.assertEqual(starts, [0])

    def test_live_increase_postpones_collection_without_restart(self):
        starts, _ = self.run_schedule(5, 900, change=(240, 60))
        self.assertEqual(starts, [0])

    def test_live_decrease_uses_elapsed_time_without_bursting(self):
        starts, _ = self.run_schedule(60, 960, change=(600, 5))
        self.assertEqual(starts, [0, 600, 900])


if __name__ == "__main__":
    unittest.main()
