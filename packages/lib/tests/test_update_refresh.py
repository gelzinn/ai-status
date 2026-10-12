"""Usage refreshes discover new releases without waiting for a separate timer."""

import contextlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, daemon, fetch, quickshell, state


class RefreshUpdateChecksTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ai-status-refresh-version-")
        self.addCleanup(temporary.cleanup)
        self.providers = Path(temporary.name)
        self.data = {"provider": "Codex", "metrics": [{"type": "weekly", "percentage": 42}]}
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for mock in (
            patch.object(fetch.cfgmod, "providers_dir", return_value=str(self.providers)),
            patch.object(fetch.cfgmod, "enabled_connections", return_value=[{"provider": "codex", "connection_id": "codex"}]),
            patch.object(fetch, "run_provider", side_effect=lambda *_: dict(self.data)),
            patch.object(fetch, "_latest_version", None),
            patch.object(fetch, "__version__", "1.0.0"),
        ):
            self.stack.enter_context(mock)

    def test_each_refresh_discovers_the_new_release_and_exposes_the_notice(self):
        responses = [json.dumps({"tag_name": tag, "draft": False, "prerelease": False})
                     for tag in ("v1.0.0", "v1.0.1", "v1.0.2")]
        with patch.object(fetch, "request", side_effect=responses) as request:
            for version, has_update in (("1.0.0", False), ("1.0.1", True), ("1.0.2", True)):
                data = fetch.fetch_all_data(check_updates=True)
                self.assertEqual(data[0]["metrics"], self.data["metrics"])
                self.assertEqual(fetch.get_version_info(), {
                    "current": "1.0.0", "latest": version, "has_update": has_update,
                })
                with patch.object(fetch.cfgmod, "available_providers", return_value=[]):
                    self.assertEqual(quickshell.build_snapshot([], {})["version"]["latest"], version)
            self.assertEqual(request.call_count, 3)

    def test_slow_release_check_does_not_delay_streamed_usage_results(self):
        started, streamed = threading.Event(), threading.Event()
        release_waits = []

        def release_check():
            started.set()
            release_waits.append(streamed.wait(3))

        def provider(*_):
            self.assertTrue(started.wait(3))
            return dict(self.data)

        def on_result(name, providers):
            self.assertEqual(name, "codex")
            self.assertEqual(providers[0]["metrics"], self.data["metrics"])
            streamed.set()

        with patch.object(fetch, "check_for_updates", side_effect=release_check), \
                patch.object(fetch, "run_provider", side_effect=provider):
            self.assertEqual(len(fetch.fetch_all_data(on_result=on_result, check_updates=True)), 1)
        self.assertTrue(streamed.is_set())
        self.assertEqual(release_waits, [True], "Usage must stream before the release check finishes")

    def test_unavailable_release_api_keeps_usage_and_the_last_known_notice(self):
        with patch.object(fetch, "_latest_version", "1.0.1"), \
                patch.object(fetch, "request", side_effect=OSError("GitHub unavailable")):
            self.assertEqual(len(fetch.fetch_all_data(check_updates=True)), 1)
            self.assertTrue(fetch.get_version_info()["has_update"])
            self.assertEqual(fetch.get_version_info()["latest"], "1.0.1")

    def test_release_is_checked_even_without_enabled_providers(self):
        with patch.object(fetch.cfgmod, "enabled_connections", return_value=[]), \
                patch.object(fetch, "request", return_value=json.dumps({"tag_name": "v1.0.1"})) as request:
            self.assertEqual(fetch.fetch_all_data(check_updates=True), [])
            request.assert_called_once()
            self.assertTrue(fetch.get_version_info()["has_update"])

    def test_plain_usage_queries_do_not_gain_an_unrequested_network_operation(self):
        with patch.object(fetch, "request") as request:
            self.assertEqual(len(fetch.fetch_all_data()), 1)
            request.assert_not_called()

    def test_each_daemon_refresh_requests_a_release_check_on_every_platform(self):
        for output_format in ("waybar", "quickshell", "macos"):
            with self.subTest(output_format=output_format), \
                    patch.object(state, "acquire_lock", return_value=True), \
                    patch.object(state, "release_lock"), patch.object(state, "save_cache"), \
                    patch.object(fetch, "fetch_all_data", return_value=[]) as collect:
                daemon.update_task(output_format)
                daemon.update_task(output_format)
                self.assertEqual(collect.call_count, 2)
                self.assertTrue(all(call.kwargs["check_updates"] for call in collect.call_args_list))

    def test_swiftbar_refresh_requests_the_same_release_check(self):
        with patch.object(state, "acquire_lock", return_value=True), \
                patch.object(state, "release_lock") as unlock, patch.object(state, "save_cache"), \
                patch.object(fetch, "fetch_all_data", return_value=[]) as collect:
            cli._swiftbar_refresh()
        collect.assert_called_once_with(include_errors=True, check_updates=True)
        unlock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
