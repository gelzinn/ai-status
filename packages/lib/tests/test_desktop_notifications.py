"""Desktop delivery failures never affect collection; macOS outbox survives restarts."""
import importlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import desktop_notifications, notifications, paths


EVENT = {"id": "event-1", "title": "AI Status · Quota alert",
         "body": "Claude personal: 95% of Weekly quota used. Resets in 2d.",
         "kind": "threshold", "provider": "account:personal", "idx": 0,
         "metric": "weekly", "threshold": 95}


class DesktopDeliveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        directory_patch = patch.object(paths, "CONFIG_DIR", Path(directory.name))
        directory_patch.start()
        self.addCleanup(directory_patch.stop)

    def test_linux_uses_argument_vector_and_reports_os_acceptance(self):
        event = dict(EVENT, title="--help", body='$(touch /tmp/unsafe) <b>Quota</b>')
        notifier = MagicMock(stdout=io.BytesIO(b""))
        notifier.wait.return_value = 1
        notifier.poll.return_value = 1
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(desktop_notifications.deliver(event))
        args, options = run.call_args
        self.assertEqual(args[0][-3:], ["--", event["title"], event["body"]])
        self.assertIn("--app-name=AI Status", args[0])
        self.assertIn("--urgency=normal", args[0])
        self.assertNotIn("shell", options)
        self.assertEqual(options["timeout"], 3)

    def test_exhaustion_is_critical_and_missing_or_hanging_notifier_returns_false(self):
        notifier = MagicMock(stdout=io.BytesIO(b""))
        notifier.wait.return_value = 1
        notifier.poll.return_value = 1
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 1)) as run:
            self.assertFalse(desktop_notifications.deliver(dict(EVENT, threshold=100)))
            self.assertIn("--urgency=critical", run.call_args.args[0])
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("notify-send", 3)):
            with self.subTest(error=type(error).__name__), patch.object(sys, "platform", "linux"), \
                    patch.object(subprocess, "Popen", side_effect=error):
                self.assertFalse(desktop_notifications.deliver(EVENT))

    def test_macos_durable_queue_is_idempotent_and_acknowledges_only_requested_ids(self):
        with patch.object(sys, "platform", "darwin"), patch.object(desktop_notifications.time, "time", return_value=1000):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertTrue(desktop_notifications.deliver(dict(EVENT, id="event-2"), frontend="macos"))
            # Recreating the adapter leaves its on-disk outbox available.
            importlib.reload(desktop_notifications)
            self.assertEqual([event["id"] for event in desktop_notifications.pending()], ["event-1", "event-2"])
            desktop_notifications.ack(["event-1"])
            self.assertEqual([event["id"] for event in desktop_notifications.pending()], ["event-2"])
            desktop_notifications.ack(["unknown"])
            self.assertEqual(len(desktop_notifications.pending()), 1)

    def test_old_events_are_not_delivered_after_reconnecting(self):
        with patch.object(sys, "platform", "darwin"), patch.object(desktop_notifications.time, "time", return_value=1000):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
        with patch.object(desktop_notifications.time, "time", return_value=1301):
            self.assertEqual(desktop_notifications.pending(), [])

    def test_new_fresh_observation_discards_an_obsolete_threshold(self):
        now = 1000
        entry = {"_dir": "claude", "_connection_id": "account:personal", "_idx": 0,
                 "_observed_at": now, "_fingerprint": "same-account",
                 "metrics": [{"type": "weekly", "percentage": 20}]}
        with patch.object(sys, "platform", "darwin"), patch.object(desktop_notifications.time, "time", return_value=now):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertEqual(desktop_notifications.pending([entry]), [])
            entry["metrics"][0]["percentage"] = 99
            self.assertEqual(desktop_notifications.pending([entry]), [])

    def test_failed_or_cached_snapshot_does_not_invent_a_new_quota_observation(self):
        for flags in ({"_cached": True}, {"_error": "offline"}, {"_observed_at": 1}):
            with self.subTest(flags=flags), patch.object(sys, "platform", "darwin"), \
                    patch.object(desktop_notifications.time, "time", return_value=1000):
                self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
                entry = {"_dir": "claude", "_connection_id": "account:personal", "_idx": 0,
                         "_observed_at": 1000, "_fingerprint": "same-account",
                         "metrics": [{"type": "weekly", "percentage": 20}], **flags}
                self.assertEqual([event["id"] for event in desktop_notifications.pending([entry])], ["event-1"])
                desktop_notifications.ack(["event-1"])

    def test_recovery_is_discarded_when_new_data_is_blocked_or_incomplete(self):
        for metrics in ([{"type": "rolling", "percentage": 100}, {"type": "weekly", "percentage": 20}],
                        [{"type": "rolling", "percentage": 0}],
                        [{"type": "rolling", "percentage": 0}, {"type": "weekly", "percentage": None}]):
            with self.subTest(metrics=metrics), patch.object(sys, "platform", "darwin"), \
                    patch.object(desktop_notifications.time, "time", return_value=1000):
                event = dict(EVENT, kind="recovery", metric="rolling", observed_metrics=["rolling", "weekly"])
                self.assertTrue(desktop_notifications.deliver(event, frontend="macos"))
                entry = {"_dir": "claude", "_connection_id": "account:personal", "_idx": 0,
                         "_observed_at": 1000, "_fingerprint": "same-account", "metrics": metrics}
                self.assertEqual(desktop_notifications.pending([entry]), [])

    def test_new_credentials_invalidate_queued_notifications_for_previous_login(self):
        with patch.object(sys, "platform", "darwin"), patch.object(desktop_notifications.time, "time", return_value=1000):
            self.assertTrue(desktop_notifications.deliver(dict(EVENT, fingerprint="previous-login"), frontend="macos"))
            entry = {"_dir": "claude", "_connection_id": "account:personal", "_idx": 0,
                     "_observed_at": 1000, "_fingerprint": "new-login", "metrics": [{"type": "weekly", "percentage": 99}]}
            self.assertEqual(desktop_notifications.pending([entry]), [])

    def test_same_account_token_refresh_preserves_a_relevant_queued_notification(self):
        with patch.object(sys, "platform", "darwin"), patch.object(desktop_notifications.time, "time", return_value=1000):
            self.assertTrue(desktop_notifications.deliver(dict(EVENT, identity="same-account", fingerprint="old-token"), frontend="macos"))
            entry = {"_dir": "claude", "_connection_id": "account:personal", "_idx": 0,
                     "_observed_at": 1000, "_fingerprint": "new-token", "_notification_identity": "same-account",
                     "metrics": [{"type": "weekly", "percentage": 99}]}
            self.assertEqual([event["id"] for event in desktop_notifications.pending([entry])], ["event-1"])

    def test_silencing_drops_queued_events_without_a_catchup_burst(self):
        with patch.object(sys, "platform", "darwin"):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
        notifications.save_settings({"enabled": False})
        self.assertEqual(desktop_notifications.pending(), [])
        notifications.save_settings({"enabled": True})
        self.assertEqual(desktop_notifications.pending(), [])

    def test_rule_disabled_before_submission_drops_only_its_window(self):
        with patch.object(sys, "platform", "darwin"):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertTrue(desktop_notifications.deliver(dict(EVENT, id="rolling", metric="rolling"), frontend="macos"))
        notifications.save_settings({"rules": [{"connection_id": "account:personal", "metric": "weekly", "enabled": False}]})
        self.assertEqual([event["id"] for event in desktop_notifications.pending()], ["rolling"])

    def test_changed_threshold_and_recovery_preferences_drop_pending_alerts(self):
        with patch.object(sys, "platform", "darwin"):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertTrue(desktop_notifications.deliver(dict(EVENT, id="recovered", kind="recovery"), frontend="macos"))
        notifications.save_settings({"thresholds": [100], "recovery": False})
        self.assertEqual(desktop_notifications.pending(), [])
        notifications.save_settings({"thresholds": [95], "recovery": True})
        self.assertEqual(desktop_notifications.pending(), [])

    def test_queue_write_failure_or_lock_contention_is_a_harmless_delivery_failure(self):
        with patch.object(sys, "platform", "darwin"), patch.object(paths, "atomic_json", side_effect=OSError("read only")):
            self.assertFalse(desktop_notifications.deliver(EVENT, frontend="macos"))
        with desktop_notifications._locked(), patch.object(sys, "platform", "darwin"):
            self.assertFalse(desktop_notifications.deliver(EVENT, frontend="macos"))
            self.assertEqual(desktop_notifications.pending(), [])

    def test_invalid_queue_entries_and_events_are_ignored(self):
        paths.atomic_json(desktop_notifications.queue_file(), {"events": [None, EVENT, {**EVENT, "queued_at": "today"}]})
        self.assertEqual(desktop_notifications.pending(), [])
        self.assertFalse(desktop_notifications.deliver({"title": "quota"}))
        with self.assertRaises(ValueError):
            desktop_notifications.ack([1])


if __name__ == "__main__":
    unittest.main()
