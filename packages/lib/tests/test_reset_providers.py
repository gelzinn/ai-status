"""Reset mutations use mocked HTTP and fixture credentials exclusively."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from test_portability import load_provider
from core.provider_http import QueryError

REQUEST_ID = "be2febc8-0b73-4e1d-829c-0313533f1819"
FUTURE = "2099-10-22T16:00:00Z"
PAST = "2000-01-01T00:00:00Z"
ORGANIZATION = "3949c683-2abc-48aa-8d55-5ca849c81df5"


def handle(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def codex_details(**overrides):
    credit = {"id": "credit-fixture", "reset_type": "codex_rate_limits",
              "status": "available", "expires_at": FUTURE, **overrides}
    return {"available_count": 1, "credits": [credit]}


def claude_usage(**overrides):
    grant = {"id": "grant-fixture", "resets_left": 2, "usable_now": True,
             "paused": False, "ends_at": FUTURE, "use_requires_limit": True,
             "blocking": [], **overrides}
    return {"cedar_ember": {"eligible": True, "at_limit": True,
                            "next_grant_id": "grant-fixture", "grants": [grant]}}


class CodexResetProviderTests(unittest.TestCase):
    def setUp(self):
        self.module = load_provider("codex", "reset")
        self.env = {"AI_STATUS_ACCOUNT_ID": "fixture", "CODEX_ACCESS_TOKEN": "fixture-token",
                    "CODEX_ACCOUNT_ID": "fixture-account"}

    def test_selected_credit_body_account_and_callbacks_precede_one_post(self):
        events = []

        def request(url, headers, **options):
            events.append(options.get("method", "GET"))
            if options.get("method") == "POST":
                self.assertEqual(url, self.module.CONSUME_URL)
                self.assertEqual(headers["Authorization"], "Bearer fixture-token")
                self.assertEqual(headers["ChatGPT-Account-Id"], "fixture-account")
                self.assertEqual(headers["Content-Type"], "application/json")
                self.assertEqual(json.loads(options["data"]),
                                 {"redeem_request_id": REQUEST_ID, "credit_id": "credit-fixture"})
                return '{"code":"reset"}'
            self.assertEqual(url, self.module.RESET_CREDITS_URL)
            return json.dumps(codex_details())

        with patch.object(self.module, "request", side_effect=request) as api:
            self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID,
                                verify_identity=lambda: events.append("verify"),
                                before_send=lambda: events.append("reserve"))
        self.assertEqual(events, ["GET", "verify", "reserve", "POST"])
        self.assertEqual(api.call_count, 2)

    def test_same_nonce_is_forwarded_unchanged_for_same_logical_attempt(self):
        responses = [json.dumps(codex_details()), '{"code":"reset"}',
                     json.dumps(codex_details()), '{"code":"already_redeemed"}']
        with patch.object(self.module, "request", side_effect=responses) as api:
            for _ in range(2):
                self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
        bodies = [json.loads(call.kwargs["data"]) for call in api.call_args_list if call.kwargs.get("method") == "POST"]
        self.assertEqual([body["redeem_request_id"] for body in bodies], [REQUEST_ID, REQUEST_ID])
        self.assertEqual([body["credit_id"] for body in bodies], ["credit-fixture", "credit-fixture"])

    def test_changed_login_callback_stops_before_post_and_reservation(self):
        reservation = Mock()
        verify = Mock(side_effect=ValueError("Account login changed"))
        with patch.object(self.module, "request", return_value=json.dumps(codex_details())) as api:
            with self.assertRaisesRegex(ValueError, "login changed"):
                self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID,
                                    verify_identity=verify, before_send=reservation)
        api.assert_called_once()
        reservation.assert_not_called()

    def test_headers_are_captured_before_inventory_and_never_reread_for_post(self):
        def rotate_environment():
            self.env["CODEX_ACCESS_TOKEN"] = "rotated-token"
            self.env["CODEX_ACCOUNT_ID"] = "rotated-account"

        with patch.dict(os.environ, {"CODEX_ACCESS_TOKEN": "ambient-token", "CODEX_ACCOUNT_ID": "ambient-account"}), \
                patch.object(self.module, "request", side_effect=[json.dumps(codex_details()), '{"code":"reset"}']) as api:
            self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID, verify_identity=rotate_environment)
        for call in api.call_args_list:
            self.assertEqual(call.args[1]["Authorization"], "Bearer fixture-token")
            self.assertEqual(call.args[1]["ChatGPT-Account-Id"], "fixture-account")

    def test_missing_explicit_account_header_stops_without_any_http(self):
        self.env.pop("CODEX_ACCOUNT_ID")
        with patch.object(self.module, "request") as api, self.assertRaises(QueryError):
            self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
        api.assert_not_called()

    def test_fresh_spent_expired_unknown_type_and_wrong_credit_never_post(self):
        for overrides in ({"status": "redeemed"}, {"expires_at": PAST}, {"expires_at": "invalid"},
                          {"reset_type": "future_type"}, {"id": "different-credit"}):
            with self.subTest(overrides=overrides), \
                    patch.object(self.module, "request", return_value=json.dumps(codex_details(**overrides))) as api:
                with self.assertRaises(QueryError):
                    self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
                api.assert_called_once()

    def test_no_verified_count_or_bad_inventory_never_posts(self):
        for data in ([], None, {"available_count": 0, "credits": codex_details()["credits"]},
                     {"available_count": 1, "credits": None}):
            with self.subTest(data=data), patch.object(self.module, "request", return_value=json.dumps(data)) as api:
                with self.assertRaises(QueryError):
                    self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
                api.assert_called_once()

    def test_known_nonconsumption_outcomes_are_reported_and_never_retried(self):
        for code in ("no_credit", "nothing_to_reset"):
            with self.subTest(code=code), patch.object(self.module, "request",
                    side_effect=[json.dumps(codex_details()), json.dumps({"code": code})]) as api:
                with self.assertRaises(QueryError) as caught:
                    self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
                self.assertEqual(caught.exception.reset_outcome, code)
                self.assertFalse(getattr(caught.exception, "reset_uncertain", False))
                self.assertEqual(api.call_count, 2)

    def test_uncertain_response_is_not_retried_or_interpreted_as_failure_to_consume(self):
        for response in (QueryError("unreachable"), "invalid JSON", '{"code":"future_code"}', '{"code":[]}'):
            with self.subTest(response=response), patch.object(self.module, "request",
                    side_effect=[json.dumps(codex_details()), response]) as api:
                with self.assertRaises(QueryError) as caught:
                    self.module.consume(self.env, handle("credit-fixture"), REQUEST_ID)
                self.assertTrue(caught.exception.reset_uncertain)
                self.assertEqual(api.call_count, 2)


class ClaudeResetProviderTests(unittest.TestCase):
    def setUp(self):
        self.module = load_provider("claude", "reset")
        self.env = {"AI_STATUS_ACCOUNT_ID": "fixture", "CLAUDE_ACCESS_TOKEN": "fixture-token"}
        self.profile = {"organization": {"uuid": ORGANIZATION}}

    def test_profile_for_same_bearer_binds_org_grant_and_nonce_to_one_post(self):
        events = []
        with patch.object(self.module, "request", side_effect=[json.dumps(self.profile),
                          json.dumps(claude_usage()), '{"result":"reset"}']) as api:
            self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID,
                                verify_identity=lambda: events.append("verify"),
                                before_send=lambda: events.append("reserve"))
        self.assertEqual(events, ["verify", "reserve"])
        self.assertEqual(api.call_args_list[0].args[0], self.module.PROFILE_URL)
        self.assertEqual(api.call_args_list[1].args[0], self.module.USAGE_URL)
        post = api.call_args_list[2]
        self.assertEqual(post.args[0], f"https://api.anthropic.com/api/organizations/{ORGANIZATION}/reset_rate_limits")
        self.assertEqual(post.kwargs["method"], "POST")
        self.assertEqual(json.loads(post.kwargs["data"]),
                         {"program": "cedar_ember", "grant_id": "grant-fixture", "request_id": REQUEST_ID})
        for call in api.call_args_list:
            self.assertEqual(call.args[1]["Authorization"], "Bearer fixture-token")
            self.assertEqual(call.args[1]["anthropic-beta"], "oauth-2025-04-20")
            self.assertEqual(call.args[1]["Content-Type"], "application/json")

    def test_missing_or_invalid_profile_organization_never_posts(self):
        for profile in ({}, {"organization": {}}, {"organization": {"uuid": "other/path"}}, []):
            with self.subTest(profile=profile), patch.object(self.module, "request",
                    side_effect=[json.dumps(profile), json.dumps(claude_usage())]) as api:
                with self.assertRaises(QueryError):
                    self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
                self.assertTrue(all(call.kwargs.get("method", "GET") == "GET" for call in api.call_args_list))

    def test_changed_login_callback_stops_before_post_or_reservation(self):
        reservation = Mock()
        with patch.object(self.module, "request", side_effect=[json.dumps(self.profile), json.dumps(claude_usage())]) as api:
            with self.assertRaisesRegex(ValueError, "login changed"):
                self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID,
                                    verify_identity=Mock(side_effect=ValueError("Account login changed")),
                                    before_send=reservation)
        self.assertEqual(api.call_count, 2)
        reservation.assert_not_called()

    def test_service_next_grant_must_match_selected_handle(self):
        usage = claude_usage()
        usage["cedar_ember"]["next_grant_id"] = "different-grant"
        with patch.object(self.module, "request", side_effect=[json.dumps(self.profile), json.dumps(usage)]) as api:
            with self.assertRaises(QueryError):
                self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
        self.assertEqual(api.call_count, 2)

    def test_fresh_paused_spent_expired_or_blocked_grants_never_post(self):
        for overrides in ({"paused": True}, {"usable_now": False}, {"resets_left": 0},
                          {"ends_at": PAST}, {"ends_at": "invalid"}, {"starts_at": FUTURE},
                          {"blocking": ["seven_day"]}):
            with self.subTest(overrides=overrides), patch.object(self.module, "request",
                    side_effect=[json.dumps(self.profile), json.dumps(claude_usage(**overrides))]) as api:
                with self.assertRaises(QueryError):
                    self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
                self.assertEqual(api.call_count, 2)

    def test_fresh_ineligibility_cooldown_or_nonlimited_state_prevents_post(self):
        for changes in ({"eligible": False}, {"cooldown_until": FUTURE}, {"at_limit": False}):
            usage = claude_usage()
            usage["cedar_ember"].update(changes)
            with self.subTest(changes=changes), patch.object(self.module, "request",
                    side_effect=[json.dumps(self.profile), json.dumps(usage)]) as api:
                with self.assertRaises(QueryError):
                    self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
                self.assertEqual(api.call_count, 2)

    def test_anytime_grant_does_not_require_at_limit(self):
        usage = claude_usage(use_requires_limit=False)
        usage["cedar_ember"]["at_limit"] = False
        with patch.object(self.module, "request", side_effect=[json.dumps(self.profile), json.dumps(usage),
                          '{"result":"reset"}']) as api:
            self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
        self.assertEqual(api.call_count, 3)

    def test_known_outcomes_preserve_nonce_and_do_not_retry(self):
        for outcome in ("already_used", "not_limited", "cooldown", "ineligible"):
            with self.subTest(outcome=outcome), patch.object(self.module, "request",
                    side_effect=[json.dumps(self.profile), json.dumps(claude_usage()),
                                 json.dumps({"result": outcome})]) as api:
                with self.assertRaises(QueryError) as caught:
                    self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
                self.assertEqual(caught.exception.reset_outcome, outcome)
                self.assertEqual(json.loads(api.call_args.kwargs["data"])["request_id"], REQUEST_ID)
                self.assertEqual(api.call_count, 3)

    def test_unavailable_and_lost_responses_remain_uncertain_without_retry(self):
        for result in ('{"result":"unavailable"}', QueryError("unreachable"), "invalid JSON", '{"result":[]}'):
            with self.subTest(result=result), patch.object(self.module, "request",
                    side_effect=[json.dumps(self.profile), json.dumps(claude_usage()), result]) as api:
                with self.assertRaises(QueryError) as caught:
                    self.module.consume(self.env, handle("grant-fixture"), REQUEST_ID)
                self.assertTrue(caught.exception.reset_uncertain)
                self.assertEqual(api.call_count, 3)


class ResetAuthenticationAndProjectionTests(unittest.TestCase):
    def test_explicit_connection_without_credentials_never_uses_ambient_login(self):
        for provider in ("codex", "claude"):
            module = load_provider(provider)
            with self.subTest(provider=provider), patch.dict(os.environ,
                    {"CODEX_ACCESS_TOKEN": "ambient", "CLAUDE_ACCESS_TOKEN": "ambient"}), \
                    patch.object(module, "read_json") as read:
                with self.assertRaises(QueryError):
                    module.authentication({"AI_STATUS_ACCOUNT_ID": "fixture"})
                read.assert_not_called()

    def test_captured_custom_home_is_used_without_resolving_ambient_home(self):
        for provider, data, relative in (
                ("codex", {"tokens": {"access_token": "fixture", "account_id": "fixture-account"}}, ".codex/auth.json"),
                ("claude", {"claudeAiOauth": {"accessToken": "fixture"}}, ".claude/.credentials.json")):
            module = load_provider(provider)
            with self.subTest(provider=provider), patch.object(module.Path, "home", side_effect=AssertionError("ambient home")), \
                    patch.object(module, "read_json", return_value=data) as read:
                if provider == "claude":
                    with patch.object(module.sys, "platform", "linux"):
                        module.authentication({"HOME": "/fixture-user"})
                else:
                    module.authentication({"HOME": "/fixture-user"})
            self.assertEqual(Path(read.call_args.args[0]), Path("/fixture-user") / relative)

    def test_codex_actions_require_account_header_and_known_reset_type(self):
        module = load_provider("codex")
        usage = {"rate_limit_reset_credits": {"available_count": 1}}
        for account, reset_type, expected in (("fixture-account", "codex_rate_limits", True),
                                             (None, "codex_rate_limits", False),
                                             ("fixture-account", "future_type", False)):
            env = {"CODEX_ACCESS_TOKEN": "fixture-token"}
            if account is not None:
                env["CODEX_ACCOUNT_ID"] = account
            with self.subTest(account=account, reset_type=reset_type), patch.dict(os.environ, env, clear=True), \
                    patch.object(module, "request", side_effect=[json.dumps(usage),
                          json.dumps(codex_details(reset_type=reset_type))]):
                raw = module.query()
            self.assertNotIn("credit-fixture", raw)
            credit = json.loads(raw)["rate_limit_reset_credits"]["credits"][0]
            self.assertEqual("action_id" in credit, expected)
            parsed = load_provider("codex", "parse").parse(raw)
            self.assertNotIn("credit-fixture", json.dumps(parsed))

    def test_claude_parser_retains_only_next_grant_handle_and_no_raw_id(self):
        usage = claude_usage()
        extra = deepcopy(usage["cedar_ember"]["grants"][0])
        extra["id"] = "other-grant-fixture"
        usage["cedar_ember"]["grants"].append(extra)
        parsed = load_provider("claude", "parse").parse(json.dumps(usage))
        credits = parsed["reset_credits"]["credits"]
        self.assertEqual(credits[0]["action_id"], handle("grant-fixture"))
        self.assertNotIn("action_id", credits[1])
        self.assertNotIn("grant-fixture", json.dumps(parsed))


if __name__ == "__main__":
    unittest.main()
