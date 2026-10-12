"""Monetary credit selection and live Waybar output without extra requests."""
import contextlib
from datetime import datetime, timezone
import io
import json
from unittest.mock import patch

from test_portability import IsolatedState
from core import cli, config, daemon, logos, notifications, quickshell, render, state, swiftbar, usage_credits


class CloudCreditViewTests(IsolatedState):
    def setUp(self):
        super().setUp()
        self.now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()
        self.credit = usage_credits.from_claude({"iguana_necktie": {
            "limit_dollars": 100, "remaining_dollars": 73.25,
            "resets_at": "2026-11-05T07:59:00Z"}})
        self.provider = {"provider": "Claude (Pro)", "_dir": "claude", "_idx": 0,
                         "_observed_at": self.now, "metrics": [],
                         "monetary_credits": [self.credit]}
        self.selected = {"provider": "claude", "idx": 0, "metric": "credits:claude-cloud",
                         "icon_mode": "none", "show_metric": True}
        config.save_config(["claude"])
        clock = self

        class DisplayClock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromtimestamp(clock.now, tz)

        display_clock = patch.object(usage_credits, "datetime", DisplayClock)
        display_clock.start()
        self.addCleanup(display_clock.stop)

    def test_waybar_and_swiftbar_show_money_and_expiration_without_percentage_bars(self):
        for balance, flags, value, status in ((73.25, {}, "$73.25", "Available"),
                                              (0, {}, "$0.00", "Exhausted"),
                                              (73.25, {"_cached": True}, "Unavailable", "Unavailable")):
            with self.subTest(status=status):
                data = [{**self.provider, **flags,
                         "monetary_credits": [{**self.credit, "balance": balance}]}]
                output = render.build_final_state(data, self.selected)
                self.assertIn(value, output["text"])
                self.assertIn("Cloud credits", output["tooltip"])
                self.assertIn(status, output["tooltip"])
                self.assertIn("2026-11-05T07:59:00Z", output["tooltip"])
                self.assertNotIn("█", output["tooltip"])
                menu = swiftbar.render_menu(data, self.selected)
                self.assertIn("Cloud credits:  " + value, menu)
                self.assertIn(status, menu)
                self.assertNotIn("█", menu)

    def test_cli_cycles_to_cloud_and_projection_does_not_duplicate_it(self):
        self.provider["metrics"] = [{"type": "weekly", "percentage": 42}]
        state.save_cache([self.provider])
        state.save_selected({**self.selected, "metric": "weekly"})
        cli.cycle_metric(frontend="macos")
        self.assertEqual(state.load_selected()["metric"], "credits:claude-cloud")
        projected = {**self.provider, "metrics": render.entry_metrics(self.provider)}
        self.assertEqual(len(render.entry_metrics(projected)), 2)
        self.now += 601
        self.assertEqual(render.entry_metrics(projected)[-1]["value"], "Unavailable")
        cli.cycle_metric(frontend="macos")
        self.assertEqual(state.load_selected()["metric"], "weekly")

    def test_missing_or_damaged_metric_list_does_not_hide_valid_credit(self):
        for metrics in (None, {}, "unexpected", [None]):
            with self.subTest(metrics=metrics):
                data = {**self.provider, "metrics": metrics}
                self.assertEqual(render.entry_metrics(data)[0]["amount"], 73.25)
                self.assertIn("$73.25", render.build_final_state([data], self.selected)["text"])
                self.assertEqual(quickshell.build_snapshot([data], self.selected)["providers"][0]["metrics"][0]["value"], "$73.25")

    def test_waybar_daemon_republishes_expiration_and_staleness_without_refetch(self):
        for transition in ("Expired", "Unavailable"):
            with self.subTest(transition=transition):
                start = self.now
                credit = self.credit.copy()
                if transition == "Expired":
                    credit["expires_at"] = datetime.fromtimestamp(start + 2, timezone.utc).isoformat()
                data = [{**self.provider, "_observed_at": start,
                         "monetary_credits": [credit]}]
                state.save_cache(data)
                state.save_selected(self.selected)
                end = start + (4 if transition == "Expired" else 603)

                def sleep(seconds):
                    self.now += max(seconds, 1)
                    if self.now >= end:
                        raise KeyboardInterrupt

                class ImmediateThread:
                    def __init__(self, target, args, **kwargs):
                        self.target, self.args = target, args

                    def start(self):
                        self.target(*self.args)

                def collect(_format):
                    daemon.latest_data = data
                    daemon._pending.clear()
                    daemon.is_updating = False

                output = io.StringIO()
                with patch.object(daemon.time, "time", side_effect=lambda: self.now), \
                        patch.object(daemon.time, "sleep", side_effect=sleep), \
                        patch.object(daemon.threading, "Thread", ImmediateThread), \
                        patch.object(daemon, "update_task", side_effect=collect) as fetch, \
                        patch.object(notifications, "next_check_delay", return_value=3600), \
                        patch.object(logos, "update_current"), \
                        patch.object(logos, "write_tooltip"), \
                        patch.object(logos, "signal_waybar"), \
                        contextlib.redirect_stdout(output):
                    daemon._run("waybar")
                rows = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual(len(rows), 2)
                self.assertIn("$73.25", rows[0]["text"])
                self.assertIn(transition, rows[1]["text"])
                self.assertIn("Last observed $73.25", rows[1]["tooltip"])
                fetch.assert_called_once_with("waybar")
                self.assertEqual(state.load_selected(), self.selected)
