"""Isolated reset orchestration: all provider mutations and credentials are mocked."""
import contextlib
import io
import json
import time
from unittest.mock import Mock, patch

from test_portability import IsolatedState
from core import cli, paths, reset_actions, reset_credits, state
from core.provider_http import QueryError


class ResetActionTests(IsolatedState):
    def setUp(self):
        super().setUp()
        self.addCleanup(state.release_lock)
        context = patch.object(paths, "CACHE_DIR", self.root / "cache")
        context.start()
        self.addCleanup(context.stop)
        self.connection = {"connection_id": "account:work", "provider": "codex", "account_id": "work",
                           "env": {}, "options": {}, "enabled": True}
        self.handle = reset_credits.action_id("private-credit-id")
        self.entry = {"_connection_id": "account:work", "_dir": "codex", "_idx": 0,
                      "_fingerprint": "a" * 64, "_observed_at": time.time(),
                      "reset_credits": {"available": 1, "credits": [{"title": "Full reset", "count": 1,
                                            "expires_at": "2099-01-01T00:00:00Z", "action_id": self.handle}]}}
        state.save_cache([self.entry])
        self.payload = {"provider": "account:work", "idx": 0,
                        "fingerprint": reset_actions.presentation(self.entry)["fingerprint"],
                        "credit": self.handle, "confirmed": True}
        self.provider = Mock()
        self.provider.consume.side_effect = self.consume
        for target, value in (
            ("core.reset_actions.config.enabled_connections", [self.connection]),
            ("core.reset_actions.accounts.prepare", ({"CODEX_ACCESS_TOKEN": "fake"}, "a" * 64, ["fake"])),
            ("core.reset_actions._provider", self.provider),
        ):
            item = patch(target, return_value=value)
            item.start()
            self.addCleanup(item.stop)
        refresh = patch("core.reset_actions.state.trigger_refresh")
        self.refresh = refresh.start()
        self.addCleanup(refresh.stop)

    @staticmethod
    def consume(env, handle, request_id, verify_identity, before_send):
        verify_identity()
        before_send()

    def test_confirmed_action_reserves_before_dispatch_and_cannot_repeat(self):
        self.assertIn("Reset applied", reset_actions.apply(self.payload))
        self.provider.consume.assert_called_once()
        receipt = paths.read_json(reset_actions._receipt_path("account:work"))
        self.assertEqual(receipt["token"], self.payload["fingerprint"])
        self.assertEqual(receipt["credit"], self.handle)
        self.assertNotIn("private-credit-id", json.dumps(receipt))
        self.assertIsNone(reset_actions.presentation(self.entry))
        with self.assertRaisesRegex(ValueError, "already submitted"):
            reset_actions.apply(self.payload)
        self.assertEqual(self.provider.consume.call_count, 1)
        self.refresh.assert_called_once()

    def test_cancel_or_unconfirmed_request_never_dispatches(self):
        for confirmed in (None, False, 1, "true"):
            with self.subTest(confirmed=confirmed), self.assertRaisesRegex(ValueError, "Confirm"):
                reset_actions.apply({**self.payload, "confirmed": confirmed})
        self.provider.consume.assert_not_called()
        self.refresh.assert_not_called()

    def test_expired_cached_and_old_snapshot_never_dispatch(self):
        for fields in ({"_cached": True}, {"_error": "Authentication failed"},
                       {"_observed_at": time.time() - 601}, {"_observed_at": True},
                       {"_fingerprint": "different"}):
            with self.subTest(fields=fields):
                state.save_cache([{**self.entry, **fields}])
                with self.assertRaises(ValueError):
                    reset_actions.apply(self.payload)
        self.provider.consume.assert_not_called()

    def test_wrong_credit_account_or_index_never_dispatches(self):
        for fields in ({"credit": "b" * 64}, {"provider": "codex"}, {"idx": 1}, {"idx": False}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                reset_actions.apply({**self.payload, **fields})
        self.provider.consume.assert_not_called()

    def test_credential_change_before_preflight_never_dispatches(self):
        with patch("core.reset_actions.accounts.prepare", return_value=({}, "b" * 64, [])), \
                self.assertRaisesRegex(ValueError, "login changed"):
            reset_actions.apply(self.payload)
        self.provider.consume.assert_not_called()
        self.assertFalse(reset_actions._receipt_path("account:work").exists())

    def test_credential_change_after_inventory_never_dispatches(self):
        with patch("core.reset_actions.accounts.prepare", side_effect=[({}, "a" * 64, []), ({}, "b" * 64, [])]), \
                self.assertRaisesRegex(ValueError, "login changed"):
            reset_actions.apply(self.payload)
        self.assertFalse(reset_actions._receipt_path("account:work").exists())
        self.refresh.assert_not_called()

    def test_disabled_connection_never_dispatches(self):
        with patch("core.reset_actions.config.enabled_connections", return_value=[]), self.assertRaises(ValueError):
            reset_actions.apply(self.payload)
        self.provider.consume.assert_not_called()

    def test_active_operation_never_dispatches(self):
        with patch("core.reset_actions.state.acquire_lock", return_value=False), \
                self.assertRaisesRegex(ValueError, "Another account operation"):
            reset_actions.apply(self.payload)
        self.provider.consume.assert_not_called()

    def test_lost_response_stays_reserved_and_invalidates_only_account_cache(self):
        def lost(env, handle, request_id, verify_identity, before_send):
            verify_identity()
            before_send()
            raise QueryError("Could not confirm whether the reset was applied.")
        self.provider.consume.side_effect = lost
        with patch("core.reset_actions.fetch._cache_path", return_value=str(self.root / "work-cache.json")):
            (self.root / "work-cache.json").write_text("{}", encoding="utf-8")
            (self.root / "other-cache.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Could not confirm"):
                reset_actions.apply(self.payload)
        self.assertFalse((self.root / "work-cache.json").exists())
        self.assertTrue((self.root / "other-cache.json").exists())
        self.assertIsNone(reset_actions.presentation(self.entry))
        self.refresh.assert_called_once()

    def test_preflight_failure_does_not_reserve_or_invalidate(self):
        self.provider.consume.side_effect = QueryError("No verified reset credits")
        with self.assertRaisesRegex(ValueError, "No verified"):
            reset_actions.apply(self.payload)
        self.assertFalse(reset_actions._receipt_path("account:work").exists())
        self.refresh.assert_not_called()

    def test_new_observation_changes_action_token(self):
        reset_actions.apply(self.payload)
        refreshed = {**self.entry, "_observed_at": self.entry["_observed_at"] + 0.001}
        with patch("core.reset_actions.time.time", return_value=refreshed["_observed_at"]):
            self.assertNotEqual(reset_actions.presentation(refreshed)["fingerprint"], self.payload["fingerprint"])

    def test_malformed_receipt_is_not_actionable(self):
        paths.atomic_json(reset_actions._receipt_path("account:work"), [])
        self.assertIsNone(reset_actions.presentation(self.entry))

    def test_refresh_signal_failure_does_not_mask_confirmed_reset(self):
        self.refresh.side_effect = OSError("read-only")
        self.assertIn("Reset applied", reset_actions.apply(self.payload))

    def test_cli_invalid_json_never_calls_backend(self):
        with patch("core.reset_actions.apply") as apply, contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cli.main(["apply-reset", "--request-json", "invalid"]), 1)
        apply.assert_not_called()
        self.assertIn("Invalid reset request JSON", errors.getvalue())

    def test_claude_only_next_eligible_grant_gets_handle(self):
        block = {"cedar_ember": {"eligible": True, "next_grant_id": "next", "grants": [
            {"id": "next", "label": "Current", "resets_left": 2, "usable_now": True},
            {"id": "later", "label": "Later", "resets_left": 1, "usable_now": True}]}}
        parsed = reset_credits.from_claude(block)
        self.assertEqual(parsed["credits"][0]["action_id"], reset_credits.action_id("next"))
        self.assertNotIn("action_id", parsed["credits"][1])
