"""Linux action listeners accept a notification before waiting for user input."""
import io
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

from test_portability import IsolatedState
from core import config, desktop_notifications, paths, state


EVENT = {"id": "codex-weekly-95", "title": "AI Status", "body": "Codex: 95% of weekly quota used.",
         "kind": "threshold", "threshold": 95, "provider": "codex", "idx": 0, "metric": "weekly"}


class FakeNotifier:
    def __init__(self, identity=b"42\n", action=b"", returncode=None, wait_for_action=False):
        self.stdout = io.BytesIO(identity)
        self.action = action
        self.returncode = returncode
        self.released = threading.Event()
        self.waiting = threading.Event()
        self.killed = threading.Event()
        self.finished = threading.Event()
        if not wait_for_action:
            self.released.set()

    def communicate(self, timeout):
        self.waiting.set()
        if not self.released.wait(timeout):
            raise subprocess.TimeoutExpired("notify-send", timeout)
        if self.returncode is None:
            self.returncode = 0
        self.finished.set()
        return self.action, None

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def kill(self):
        self.returncode = -9
        self.killed.set()
        self.released.set()


class LinuxNotificationActionTests(IsolatedState):
    def setUp(self):
        super().setUp()
        config.save_config(["codex"])
        state.save_cache([{"provider": "Codex", "_dir": "codex", "_idx": 0,
                           "metrics": [{"type": "weekly", "percentage": 95}]}])
        state.save_selected({"provider": "codex", "idx": 0, "metric": "rolling"})

    def test_acceptance_returns_before_click_and_action_selects_existing_metric(self):
        notifier = FakeNotifier(wait_for_action=True)
        self.addCleanup(notifier.released.set)
        activated = threading.Event()
        original_activate = desktop_notifications._activate_linux

        def activate(event):
            original_activate(event)
            activated.set()

        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier) as popen, \
                patch.object(desktop_notifications, "_activate_linux", side_effect=activate):
            self.assertTrue(desktop_notifications.deliver(EVENT, frontend="quickshell"))
            self.assertTrue(notifier.waiting.wait(1))
            self.assertFalse(notifier.finished.is_set())
            self.assertEqual(state.load_selected()["metric"], "rolling")
            notifier.action = b"default\n"
            notifier.released.set()
            self.assertTrue(activated.wait(1))
        self.assertEqual(state.load_selected()["metric"], "weekly")
        activation = paths.read_json(paths.RUNTIME_DIR / "notification-activation.json")
        for key in ("id", "provider", "idx", "metric"):
            self.assertEqual(activation[key], EVENT[key])
        self.assertIsInstance(activation["time"], float)
        arguments = popen.call_args.args[0]
        self.assertIn("--print-id", arguments)
        self.assertIn("--action=default=Open", arguments)
        self.assertIn("--wait", arguments)
        self.assertIn("--icon=" + str(paths.LIB_DIR / "assets/app.png"), arguments)
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_shell_syntax_and_option_like_content_remain_literal_arguments(self):
        notifier = FakeNotifier()
        event = dict(EVENT, title="--help", body="$(touch /tmp/unsafe); `uname`")
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier) as popen:
            self.assertTrue(desktop_notifications.deliver(event))
        self.assertEqual(popen.call_args.args[0][-3:], ["--", event["title"], event["body"]])
        self.assertNotIn("shell", popen.call_args.kwargs)

    def test_rejected_action_options_retry_plain_delivery_only_before_acceptance(self):
        notifier = FakeNotifier(identity=b"", returncode=1)
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertTrue(desktop_notifications.deliver(EVENT))
        arguments = run.call_args.args[0]
        self.assertNotIn("--print-id", arguments)
        self.assertNotIn("--wait", arguments)
        self.assertEqual(arguments[-3:], ["--", EVENT["title"], EVENT["body"]])

    def test_server_rejecting_actions_after_acceptance_does_not_duplicate_notification(self):
        notifier = FakeNotifier(returncode=1)
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run") as run:
            self.assertTrue(desktop_notifications.deliver(EVENT))
        run.assert_not_called()

    def test_invalid_acknowledgment_without_rejection_is_not_assumed_delivered(self):
        notifier = FakeNotifier(identity=b"0\n", returncode=0)
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run") as run:
            self.assertFalse(desktop_notifications.deliver(EVENT))
        run.assert_not_called()

    def test_unknown_action_does_not_change_selected_metric(self):
        notifier = FakeNotifier(action=b"dismissed\n")
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier):
            self.assertTrue(desktop_notifications.deliver(EVENT))
            self.assertTrue(notifier.finished.wait(1))
        self.assertEqual(state.load_selected()["metric"], "rolling")
        self.assertFalse((paths.RUNTIME_DIR / "notification-activation.json").exists())

    def test_notification_click_rejects_disabled_or_missing_metric(self):
        for event, order in ((EVENT, []), (dict(EVENT, metric="monthly"), ["codex"]),
                             (dict(EVENT, idx=-1), ["codex"])):
            with self.subTest(event=event, order=order):
                config.save_config(order)
                desktop_notifications._activate_linux(event)
                self.assertEqual(state.load_selected()["metric"], "rolling")
                self.assertFalse((paths.RUNTIME_DIR / "notification-activation.json").exists())

    def test_timeout_waiting_for_click_reaps_listener(self):
        notifier = FakeNotifier(wait_for_action=True)
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(desktop_notifications, "LINUX_ACTION_WAIT_SECONDS", 0.01):
            self.assertTrue(desktop_notifications.deliver(EVENT))
            self.assertTrue(notifier.killed.wait(1))
        self.assertFalse((paths.RUNTIME_DIR / "notification-activation.json").exists())

    def test_handshake_timeout_does_not_retry_an_unknown_delivery(self):
        notifier = FakeNotifier(wait_for_action=True)

        class WaitingIdentity(io.BytesIO):
            def readline(self):
                notifier.released.wait(1)
                return b""

        notifier.stdout = WaitingIdentity()
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier), \
                patch.object(subprocess, "run") as run, \
                patch.object(desktop_notifications, "LINUX_HANDSHAKE_SECONDS", 0.01):
            self.assertFalse(desktop_notifications.deliver(EVENT))
            self.assertTrue(notifier.killed.is_set())
        run.assert_not_called()

    def test_shutdown_reaps_outstanding_notification_listener(self):
        notifier = FakeNotifier(wait_for_action=True)
        with patch.object(sys, "platform", "linux"), \
                patch.object(subprocess, "Popen", return_value=notifier):
            self.assertTrue(desktop_notifications.deliver(EVENT))
            self.assertTrue(notifier.waiting.wait(1))
            desktop_notifications._stop_linux_notifiers()
            self.assertTrue(notifier.killed.is_set())
            self.assertTrue(notifier.finished.wait(1))


if __name__ == "__main__":
    unittest.main()
