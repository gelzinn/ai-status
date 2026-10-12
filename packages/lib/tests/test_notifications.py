"""Quota transitions, persisted suppression and concurrent desktop collectors."""
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from core import notifications


class NotificationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        replacement = patch.object(notifications.paths, "CONFIG_DIR", self.root)
        replacement.start()
        self.addCleanup(replacement.stop)
        self.now = 1_000_000
        self.events = []

    def provider(self, percentage=79, *, observed=None, reset=None, metrics=None, **extra):
        return {"provider": "Claude", "_dir": "claude", "_connection_id": "account:personal",
                "_account_label": "Personal", "_idx": 0, "_fingerprint": "credential-1",
                "_observed_at": self.now if observed is None else observed,
                "metrics": metrics if metrics is not None else [dict(type="weekly", percentage=percentage,
                                        reset_at=self.now + 172800 if reset is None else reset)], **extra}

    def deliver(self, event):
        self.events.append(event)
        return True

    def sample(self, percentage, *, advance=1, **kwargs):
        self.now += advance
        return notifications.process([self.provider(percentage, **kwargs)], self.deliver, now=self.now)

    def settings(self, **updates):
        value = deepcopy(notifications.DEFAULT_SETTINGS)
        value.update(updates)
        return notifications.save_settings(value)

    def test_crossing_and_restart_only_notify_new_thresholds(self):
        self.sample(79)
        self.sample(81)
        self.sample(82)
        self.assertEqual([event["threshold"] for event in self.events], [80])
        self.assertIn("Claude · Personal", self.events[0]["body"])
        self.assertIn("Resets in 2 days", self.events[0]["body"])
        # Processing rereads disk on each call, matching a new collector process.
        self.sample(94)
        self.sample(95)
        self.sample(99)
        self.sample(100)
        self.assertEqual([event["threshold"] for event in self.events], [80, 95, 100])
        self.assertEqual(len({event["id"] for event in self.events}), 3)

    def test_jump_reports_only_highest_crossed_limit(self):
        self.sample(79)
        self.sample(100)
        self.sample(96)
        self.assertEqual([event["threshold"] for event in self.events if event["kind"] == "threshold"], [100])

    def test_raw_fraction_does_not_round_into_exhaustion(self):
        self.sample(99.6)
        self.assertEqual([event["threshold"] for event in self.events], [95])
        self.sample(100)
        self.assertEqual([event["threshold"] for event in self.events], [95, 100])

    def test_small_percentage_dip_and_deadline_jitter_do_not_repeat(self):
        deadline = self.now + 1000
        self.sample(81, reset=deadline)
        self.sample(79, reset=deadline + 2)
        self.sample(81, reset=deadline + 1)
        self.assertEqual(len(self.events), 1)

    def test_postponed_reset_does_not_rearm_high_percentage(self):
        deadline = self.now + 10
        self.sample(95, reset=deadline)
        self.sample(96, reset=deadline + 500, advance=20)
        self.sample(96, reset=deadline + 1000)
        self.assertEqual(len(self.events), 1)
        self.assertEqual(self.events[0]["threshold"], 95)

    def test_manual_reset_and_confirmed_new_cycle_rearm(self):
        self.sample(81)
        self.sample(0)
        self.sample(81)
        self.assertEqual([event["threshold"] for event in self.events], [80, 80])
        self.assertNotEqual(self.events[0]["id"], self.events[1]["id"])
        deadline = self.now + 10
        self.sample(95, reset=deadline)
        self.sample(20, reset=deadline + 1000, advance=20)
        self.sample(81, reset=deadline + 1000)
        self.assertEqual([event["threshold"] for event in self.events], [80, 80, 95, 80])

    def test_missing_reset_never_fabricates_countdown(self):
        entry = self.provider(95)
        entry["metrics"][0].pop("reset_at")
        notifications.process([entry], self.deliver, now=self.now)
        self.assertIn("Reset time unavailable", self.events[0]["body"])
        self.assertIsNone(self.events[0]["reset_at"])

    def test_mute_consumes_current_threshold_without_replay_storm(self):
        self.settings(muted_until=self.now + 10)
        self.sample(95)
        self.now += 20
        self.sample(95)
        self.assertEqual(self.events, [])
        self.sample(100)
        self.assertEqual([event["threshold"] for event in self.events], [100])

    def test_disabled_notifications_and_disabled_window_consume_current_levels(self):
        self.settings(enabled=False)
        self.sample(81)
        self.settings(enabled=True)
        self.sample(81)
        self.assertEqual(self.events, [])
        self.settings(rules=[dict(connection_id="account:personal", metric="weekly", thresholds=[90], enabled=False)])
        self.sample(91)
        self.settings(rules=[dict(connection_id="account:personal", metric="weekly", thresholds=[90], enabled=True)])
        self.sample(92)
        self.assertEqual(self.events, [])

    def test_per_connection_and_window_rules_preserve_identity(self):
        self.settings(rules=[dict(connection_id="account:personal", metric="*", thresholds=[99]),
                             dict(connection_id="account:personal", metric="weekly", thresholds=[85])])
        self.sample(86)
        notifications.process([self.provider(81, _connection_id="account:work")], self.deliver, now=self.now)
        self.assertEqual([event["threshold"] for event in self.events], [85, 80])
        self.assertEqual([event["provider"] for event in self.events], ["account:personal", "account:work"])
        notifications.process([self.provider(99, observed=self.now + 1, _idx=1)], self.deliver, now=self.now + 1)
        self.assertEqual(self.events[-1]["idx"], 1)

    def test_quiet_and_work_hours_include_overnight_schedules(self):
        at_night = datetime(2026, 10, 12, 23, 0).timestamp()
        at_day = datetime(2026, 10, 13, 12, 0).timestamp()
        self.settings(quiet_hours={"start": "22:00", "end": "08:00"})
        self.assertTrue(notifications.is_silent(now=at_night))
        self.assertFalse(notifications.is_silent(now=at_day))
        self.settings(work_hours={"start": "09:00", "end": "18:00"})
        self.assertTrue(notifications.is_silent(now=at_night))
        self.assertFalse(notifications.is_silent(now=at_day))

    def test_offline_stale_missing_metadata_and_malformed_data_are_ignored(self):
        variants = [dict(_cached=True), dict(_error="offline"), dict(error="offline"),
                    dict(_observed_at=self.now - 601), dict(_observed_at=self.now + 6),
                    dict(_fingerprint=""), dict(_observed_at=None)]
        for values in variants:
            notifications.process([self.provider(100, **values)], self.deliver, now=self.now)
        for invalid in (True, "100", None, float("nan"), float("inf"), -1, 101, 10 ** 400):
            notifications.process([self.provider(metrics=[dict(type="weekly", percentage=invalid)],
                                                 _connection_id=str(invalid))], self.deliver, now=self.now)
        entry = self.provider(100)
        del entry["_observed_at"]
        notifications.process([entry], self.deliver, now=self.now)
        self.assertEqual(self.events, [])

    def test_amounts_and_budgets_do_not_generate_quota_alerts(self):
        metrics = [dict(type="credits", percentage=100), dict(type="balance", percentage=100),
                   dict(type="monthly", percentage=100, amount=10, limit=10, unit="USD"),
                   dict(type="monthly", percentage=100, unit="USD"),
                   dict(type="generic", percentage=100, value_format="amount_ratio")]
        notifications.process([self.provider(metrics=metrics)], self.deliver, now=self.now)
        self.assertEqual(self.events, [])

    def test_same_or_older_observation_cannot_create_false_transition(self):
        self.sample(100)
        observed = self.now
        self.sample(0, observed=observed)
        self.sample(0, observed=observed - 1)
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])
        self.sample(0)
        self.assertEqual([event["kind"] for event in self.events], ["threshold", "recovery"])

    def windows(self, short, weekly):
        return [dict(type="rolling", percentage=short, reset_at=self.now + 10),
                dict(type="weekly", percentage=weekly, reset_at=self.now + 86400)]

    def process_windows(self, short, weekly):
        self.now += 1
        return notifications.process([self.provider(metrics=self.windows(short, weekly))], self.deliver, now=self.now)

    def test_partial_recovery_explains_remaining_blocker_and_full_recovery_once(self):
        self.process_windows(100, 100)
        self.process_windows(5, 100)
        self.process_windows(10, 100)
        partials = [event for event in self.events if event["kind"] == "partial_recovery"]
        self.assertEqual(len(partials), 1)
        self.assertIn("Still blocked", partials[0]["body"])
        self.assertIn("Weekly Usage", partials[0]["body"])
        self.assertEqual(partials[0]["blocked_metrics"], ["weekly"])
        self.process_windows(20, 5)
        self.process_windows(25, 10)
        self.assertEqual(len([event for event in self.events if event["kind"] == "recovery"]), 1)
        self.process_windows(100, 100)
        self.process_windows(20, 5)
        self.assertEqual(len([event for event in self.events if event["kind"] == "recovery"]), 2)

    def test_missing_or_invalid_known_windows_cannot_claim_recovery(self):
        self.process_windows(100, 100)
        self.now += 1
        notifications.process([self.provider(metrics=[dict(type="rolling", percentage=0)])], self.deliver, now=self.now)
        self.now += 1
        notifications.process([self.provider(metrics=[dict(type="rolling", percentage=0),
                                  dict(type="weekly", percentage=None)])], self.deliver, now=self.now)
        self.assertTrue(all(event["kind"] == "threshold" for event in self.events))
        self.process_windows(0, 0)
        self.assertEqual(self.events[-1]["kind"], "recovery")

    def test_scoped_model_alert_and_remaining_blocker_identify_the_model(self):
        metrics = [dict(type="rolling", percentage=100), dict(type="weekly", percentage=20),
                   dict(type="weekly", percentage=100, detail="Fable · Resets tomorrow")]
        notifications.process([self.provider(metrics=metrics)], self.deliver, now=self.now)
        scoped = [event for event in self.events if event["metric"] == "weekly:Fable"]
        self.assertEqual(len(scoped), 1)
        self.assertIn("Weekly Usage · Fable", scoped[0]["body"])
        metrics[0]["percentage"] = 0
        self.now += 1
        notifications.process([self.provider(metrics=metrics)], self.deliver, now=self.now)
        self.assertEqual(self.events[-1]["kind"], "partial_recovery")
        self.assertIn("exhausted Weekly Usage · Fable quota", self.events[-1]["body"])

    def test_timer_expiry_alone_and_cached_zero_cannot_claim_recovery(self):
        self.sample(100, reset=self.now + 2)
        self.now += 20
        notifications.process([self.provider(0, _cached=True)], self.deliver, now=self.now)
        self.sample(100)
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])

    def test_muted_recovery_is_not_replayed_after_unmute(self):
        self.sample(100)
        self.settings(muted_until=self.now + 10)
        self.sample(0)
        self.now += 20
        self.sample(0)
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])

    def test_failed_threshold_and_recovery_delivery_retry_on_next_fresh_sample(self):
        notifications.process([self.provider(100)], lambda event: False, now=self.now)
        self.sample(100)
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])
        self.now += 1
        notifications.process([self.provider(0)], lambda event: False, now=self.now)
        self.sample(0)
        self.sample(0)
        self.assertEqual([event["kind"] for event in self.events], ["threshold", "recovery"])

    def test_recovery_recent_only_uses_observed_activity(self):
        self.settings(recent_only=True)
        self.sample(100)
        self.sample(100, advance=86401)
        self.sample(0)
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])
        self.sample(100)
        self.sample(0)
        self.assertEqual([event["kind"] for event in self.events], ["threshold", "threshold", "recovery"])

    def test_changed_credentials_cannot_recover_previous_account_episode(self):
        self.sample(100)
        self.sample(0, _fingerprint="credential-2")
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])

    def test_stable_notification_identity_survives_automatic_credential_refresh(self):
        self.sample(95, _notification_identity="same-account")
        self.sample(95, _notification_identity="same-account", _fingerprint="refreshed-token")
        self.assertEqual([event["kind"] for event in self.events], ["threshold"])
        self.sample(100, _notification_identity="same-account", _fingerprint="refreshed-token")
        self.sample(0, _notification_identity="different-account", _fingerprint="another-token")
        self.assertEqual([event["kind"] for event in self.events], ["threshold", "threshold"])

    def test_permission_or_transport_failure_never_interrupts_collector(self):
        with patch.object(notifications.paths, "atomic_json", side_effect=PermissionError("read-only")):
            self.assertEqual(notifications.process([self.provider(100)], self.deliver, now=self.now), [])
        self.assertEqual(self.events, [])
        with patch.object(notifications, "_locked_state", side_effect=PermissionError("read-only")):
            self.assertEqual(notifications.process([self.provider(100)], self.deliver, now=self.now), [])
        self.assertEqual(notifications.process([self.provider(100)], lambda event: 1 / 0, now=self.now), [])

    def test_delivery_reservation_survives_abrupt_process_exit(self):
        def interrupted_delivery(event):
            document = json.loads((self.root / "notification-state.json").read_text(encoding="utf-8"))
            group = next(iter(document["connections"].values()))
            self.assertIn(95, group["metrics"]["weekly"]["notified"])
            raise SystemExit("collector exited after accepting notification")

        with self.assertRaises(SystemExit):
            notifications.process([self.provider(95)], interrupted_delivery, now=self.now)
        self.sample(95)
        self.assertEqual(self.events, [])

    def test_corrupted_nested_state_is_replaced_by_fresh_baseline(self):
        self.sample(81)
        state_file = self.root / "notification-state.json"
        document = json.loads(state_file.read_text(encoding="utf-8"))
        group = next(iter(document["connections"].values()))
        group["metrics"]["weekly"]["percentage"] = "corrupt"
        state_file.write_text(json.dumps(document), encoding="utf-8")
        self.sample(10)
        self.sample(95)
        self.assertEqual([event["threshold"] for event in self.events], [80, 95])

    def test_near_reset_requests_fresh_data_and_postponement_does_not_spin(self):
        entry = self.provider(100, reset=self.now + 20)
        self.assertEqual(notifications.next_check_delay([entry], now=self.now), 25)
        entry["metrics"][0]["reset_at"] = self.now - 20
        # Old response from before the deadline gets one timely confirmation.
        entry["_observed_at"] = self.now - 40
        self.assertEqual(notifications.next_check_delay([entry], now=self.now), 15)
        # A fresh response that still reports an elapsed reset uses normal
        # polling instead of querying forever every 15 seconds.
        entry["_observed_at"] = self.now
        self.assertEqual(notifications.next_check_delay([entry], now=self.now), 300)
        entry["metrics"][0]["reset_at"] = self.now + 1000
        self.assertEqual(notifications.next_check_delay([entry], now=self.now), 300)
        entry["_cached"] = True
        self.assertEqual(notifications.next_check_delay([entry], now=self.now), 300)

    def test_settings_validation_and_persistence(self):
        self.settings(thresholds=[100, 80, 95])
        self.assertEqual(notifications.load_settings()["thresholds"], [80, 95, 100])
        for invalid in (dict(thresholds=[0]), dict(thresholds=[True]), dict(thresholds=[80, 80]), dict(enabled="true"),
                        dict(muted_until=-1), dict(quiet_hours=dict(start="25:00", end="08:00")),
                        dict(work_hours=dict(start="08:00", end="")), dict(rules=[dict(connection_id="x", metric="")])):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                notifications.save_settings(invalid)
        (self.root / "notifications.json").write_text("{invalid", encoding="utf-8")
        self.assertEqual(notifications.load_settings(), notifications.DEFAULT_SETTINGS)

    def test_cross_process_lock_prevents_duplicate_desktop_delivery(self):
        script = '''
import json, sys
from pathlib import Path
from core import notifications
notifications.paths.CONFIG_DIR = Path(sys.argv[1])
entry = json.loads(sys.argv[2])
def deliver(event):
    with open(notifications.paths.CONFIG_DIR / "delivered.jsonl", "a", encoding="utf-8") as stream:
        stream.write(json.dumps(event) + "\\n")
    return True
notifications.process([entry], deliver, now=entry["_observed_at"])
'''
        environment = dict(os.environ, PYTHONPATH=str(Path(notifications.__file__).resolve().parents[1]))
        processes = [subprocess.Popen([sys.executable, "-c", script, str(self.root), json.dumps(self.provider(100))],
                                      env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual(process.returncode, 0, (stdout, stderr))
        self.assertEqual(len((self.root / "delivered.jsonl").read_text(encoding="utf-8").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
