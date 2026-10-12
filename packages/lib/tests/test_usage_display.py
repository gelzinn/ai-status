"""Used/remaining preferences change presentation without changing provider data."""
import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, config, daemon, extra_providers, fetch, macos, quickshell, render, state, swiftbar


def parse_provider(provider, payload):
    path = Path(__file__).resolve().parents[1] / "src/providers" / provider / "parse.py"
    spec = importlib.util.spec_from_file_location("usage_display_" + provider, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse(json.dumps(payload))


class UsageDisplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.config_file = root / "providers.json"
        self.selected_file = root / "selected.json"
        for replacement in (
            patch.object(config, "CONFIG_FILE", str(self.config_file)),
            patch.object(config, "available_providers", return_value=["codex", "cursor", "openrouter", "commandcode"]),
            patch.object(state, "SELECTED_FILE", str(self.selected_file)),
            patch.object(state, "CACHE_FILE", str(root / "usage.json")),
            patch.object(fetch, "get_version_info", return_value={"current": "0.13.3", "latest": "0.13.3", "has_update": False}),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        config.save_config(["codex", "cursor", "openrouter", "commandcode"])
        self.remaining = {"usage_display": "remaining"}
        self.selected = dict(provider="codex", idx=0, metric="weekly", icon_mode="off", usage_display="remaining")
        codex = parse_provider("codex", {
            "plan_type": "pro",
            "rate_limit": {"secondary_window": {"used_percent": 100, "limit_window_seconds": 604800,
                                                 "reset_after_seconds": 3600}},
            "credits": {"balance": "56167.25"},
            "rate_limit_reset_credits": {"available_count": 3},
        })
        cursor = extra_providers.parse("cursor", {
            "membershipType": "pro",
            "individualUsage": {"plan": {"autoPercentUsed": 0, "apiPercentUsed": 5},
                                "onDemand": {"used": 0}},
        })
        self.data = [dict(codex, _dir="codex", _idx=0), dict(cursor, _dir="cursor", _idx=0)]

    def test_existing_and_malformed_preferences_default_to_used(self):
        self.assertEqual(state.get_usage_display(None), "used")
        self.assertEqual(state.get_usage_display({}), "used")
        for mode in (None, "", "invalid", "Remaining", True, 1, [], {}):
            with self.subTest(mode=mode):
                self.assertEqual(state.get_usage_display({"usage_display": mode}), "used")
        self.assertEqual(state.get_usage_display(self.remaining), "remaining")
        self.assertEqual(state.get_usage_display({"usage_display": "used"}), "used")

    def test_screenshot_quotas_invert_but_credit_balances_and_reset_counts_stay_real(self):
        snapshot = quickshell.build_snapshot(self.data, self.selected)
        self.assertEqual(snapshot["text"], "Codex (Pro) 0%")
        codex, cursor = snapshot["providers"]
        self.assertEqual(codex["metrics"][0]["name"], "Weekly Remaining")
        self.assertEqual(codex["metrics"][0]["percentage"], 0)
        credits = codex["metrics"][1]
        self.assertEqual(credits["name"], "Usage credits")
        self.assertEqual(credits["value"], "56,167.25 credits")
        self.assertFalse(credits["hasPercentage"])
        self.assertEqual(codex["resetCredits"]["available"], 3)
        self.assertEqual([metric["percentage"] for metric in cursor["metrics"][:2]], [100, 95])
        self.assertEqual(cursor["metrics"][2]["value"], "$0.00")
        self.assertEqual(cursor["metrics"][2]["name"], "On-demand spend this billing cycle")

    def test_normalized_remaining_provider_percentage_is_not_inverted_twice(self):
        parsed = extra_providers.parse("ollama", {"included": {"session": {"remaining_percent": 60}}})
        metric = parsed["metrics"][0]
        self.assertEqual(metric["percentage"], 40)
        self.assertEqual(render.metric_percentage(metric, self.remaining), 60)

    def test_fractional_and_over_limit_quotas_preserve_used_data_and_bound_remaining(self):
        for used, remaining in ((0, 100), (15.25, 84.75), (100, 0), (120, 0), (-20, 100), ("25", 75)):
            with self.subTest(used=used):
                metric = {"type": "weekly", "percentage": used}
                self.assertEqual(render.metric_percentage(metric), float(used))
                self.assertEqual(render.metric_percentage(metric, self.remaining), remaining)
                self.assertEqual(metric["percentage"], used)

    def test_invalid_percentages_never_become_remaining_allowance(self):
        for invalid in (None, True, False, "invalid", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(invalid_type=type(invalid).__name__):
                metric = {"type": "weekly", "percentage": invalid, "value": "Unavailable"}
                self.assertIsNone(render.metric_percentage(metric, self.remaining))
                self.assertEqual(render.metric_value(metric, self.remaining), "Unavailable")
                self.assertEqual(render.metric_title(metric, self.remaining), "Weekly Usage")

    def test_native_snapshot_filters_invalid_metrics_instead_of_showing_false_allowance(self):
        invalid = [{"type": "weekly", "percentage": value}
                   for value in (True, False, "invalid", float("nan"), float("inf"), 10 ** 400)]
        entry = dict(self.data[0], metrics=invalid)
        snapshot = quickshell.build_snapshot([entry], self.selected)
        self.assertEqual(snapshot["providers"], [])
        self.assertEqual(snapshot["text"], "AI Status")
        json.dumps(snapshot, allow_nan=False)

    def test_failed_zero_placeholders_do_not_become_full_remaining_allowances(self):
        genuine = dict(self.data[0], metrics=[dict(type="weekly", percentage=0)])
        failed = dict(self.data[0], _idx=1, metrics=[dict(type="generic", percentage=0, detail="Authentication failed")])
        cached = dict(self.data[0], _idx=2, _cached=True, _error="Temporarily unavailable",
                      metrics=[dict(type="weekly", percentage=25)])
        snapshot = quickshell.build_snapshot([genuine, failed, cached], self.selected)
        self.assertEqual([provider["idx"] for provider in snapshot["providers"]], [0, 2])
        self.assertEqual(snapshot["text"], "Codex (Pro) 100%")
        self.assertEqual([provider["metrics"][0]["percentage"] for provider in snapshot["providers"]], [100, 75])
        self.assertEqual(snapshot["providers"][1]["error"], "Temporarily unavailable")

    def test_openrouter_credit_spend_ratio_shows_remaining_amount_with_stable_identity(self):
        parsed = parse_provider("openrouter", {"credits": {"data": {"total_credits": 100, "total_usage": 25}}})
        metric = parsed["metrics"][0]
        entry = dict(parsed, _dir="openrouter", _idx=0)
        choice = dict(self.selected, provider="openrouter", metric=render.metric_key(metric), show_metric=True)
        snapshot = quickshell.build_snapshot([entry], choice)
        visible = snapshot["providers"][0]["metrics"][0]
        self.assertEqual(visible["percentage"], 75)
        self.assertEqual(visible["value"], "$75.00 / $100.00")
        self.assertEqual(visible["name"], "Account credits remaining")
        self.assertEqual(visible["key"], "credits:Account spend / total credits (USD)")
        self.assertEqual(visible["detail"], "Available balance: $75.00")
        self.assertEqual(snapshot["text"], "OpenRouter Account credits remaining $75.00 / $100.00")
        self.assertEqual(render.metric_value(metric), "$25.00 / $100.00")

    def test_exhausted_credit_ratio_has_zero_remaining_without_altering_overdraft_detail(self):
        parsed = parse_provider("openrouter", {"credits": {"data": {"total_credits": 100, "total_usage": 120}}})
        metric = parsed["metrics"][0]
        self.assertEqual(render.metric_percentage(metric, self.remaining), 0)
        self.assertEqual(render.metric_value(metric, self.remaining), "$0.00 / $100.00")
        self.assertEqual(render.metric_value(metric), "$120.00 / $100.00")
        self.assertEqual(render.metric_detail(metric), "Available balance: $-20.00")

    def test_finite_credit_ratio_remains_convertible_when_percentage_overflows(self):
        parsed = parse_provider("openrouter", {"credits": {"data": {"total_credits": 1e-308, "total_usage": 1e308}}})
        metric = parsed["metrics"][0]
        self.assertIsNone(metric["percentage"])
        self.assertIsNone(render.metric_percentage(metric, self.remaining))
        self.assertEqual(render.metric_value(metric, self.remaining), "$0.00 / $0.00")
        self.assertEqual(render.metric_title(metric, self.remaining), "Account credits remaining")

    def test_invalid_ratio_limits_do_not_invent_a_remaining_amount(self):
        for limit in (None, 0, -1, True, "invalid", float("nan"), float("inf"), 10 ** 400):
            with self.subTest(limit_type=type(limit).__name__):
                metric = dict(type="credits", name="Credits", amount=12.5, percentage=None,
                              limit=limit, unit="USD", value_format="amount_ratio")
                self.assertEqual(render.metric_value(metric, self.remaining), "$12.50")
                self.assertEqual(render.metric_title(metric, self.remaining), "Credits")

    def test_balance_uncapped_spend_and_text_statuses_keep_values_and_titles(self):
        metrics = [
            dict(type="balance", name="Available balance", amount=-2, unit="USD", percentage=None),
            dict(type="monthly", name="Monthly spend", amount=12.5, unit="USD", percentage=None),
            dict(type="credits", name="Usage credits", value="Unlimited", percentage=None),
            dict(type="monthly", name="Included usage", value="No included allowance", percentage=None),
        ]
        for metric, value in zip(metrics, ("$-2.00", "$12.50", "Unlimited", "No included allowance")):
            with self.subTest(title=metric["name"]):
                self.assertEqual(render.metric_title(metric, self.remaining), metric["name"])
                self.assertEqual(render.metric_value(metric, self.remaining), value)
                self.assertIsNone(render.metric_percentage(metric, self.remaining))

    def test_commandcode_numeric_used_label_is_not_mislabeled_as_remaining(self):
        parsed = parse_provider("commandcode", {"windows": {"fiveHour": {"used": 0.5, "cap": 2}},
                                                 "used": 3, "remaining": 7})
        metric = parsed["metrics"][0]
        self.assertEqual(render.metric_percentage(metric, self.remaining), 75)
        self.assertEqual(render.metric_title(metric, self.remaining), "5-hour remaining")
        self.assertNotIn("$0.50", render.metric_title(metric, self.remaining))
        self.assertEqual(render.metric_key(metric), "rolling:5-hour spend: $0.50 of $2.00 used (USD)")
        self.assertEqual(render.metric_title(parsed["metrics"][1], self.remaining), "Monthly spend")
        self.assertEqual(render.metric_value(parsed["metrics"][2], self.remaining), "$7.00")

    def test_rendering_preserves_raw_cache_and_selected_metric_keys(self):
        original_data, original_selected = copy.deepcopy(self.data), copy.deepcopy(self.selected)
        state.save_cache(self.data)
        quickshell.build_snapshot(self.data, self.selected)
        render.build_final_state(self.data, self.selected)
        render.build_loading_state(self.data, 1, self.selected, pending={"cursor"})
        self.assertEqual(self.data, original_data)
        self.assertEqual(self.selected, original_selected)
        self.assertEqual(state.load_cache(), original_data)
        used = quickshell.build_snapshot(self.data, dict(self.selected, usage_display="used"))
        remaining = quickshell.build_snapshot(self.data, self.selected)
        self.assertEqual(used["selected"]["metric"], remaining["selected"]["metric"])
        self.assertEqual([metric["key"] for provider in used["providers"] for metric in provider["metrics"]],
                         [metric["key"] for provider in remaining["providers"] for metric in provider["metrics"]])

    def test_waybar_partial_loading_uses_remaining_for_completed_provider(self):
        output = render.build_loading_state(self.data, 0, self.selected, pending={"cursor"})
        tooltip = quickshell.plain_text(output["tooltip"])
        self.assertEqual(output["text"], "Codex (Pro) 0%")
        self.assertIn("Weekly Remaining", tooltip)
        self.assertIn("0%", tooltip)
        self.assertIn(render.SPINNERS[0], tooltip)
        self.assertIn("Reset credits: 3 available", tooltip)
        selected_pending = render.build_loading_state(self.data, 0, self.selected, pending={"codex"})
        self.assertEqual(selected_pending["text"], "Codex (Pro) " + render.SPINNERS[0])
        final = render.build_final_state(self.data, self.selected)
        self.assertIn("Other Models included quota remaining", quickshell.plain_text(final["tooltip"]))
        self.assertIn("95%", final["tooltip"])

    def test_first_cli_preference_before_waybar_start_still_seeds_a_provider(self):
        state.save_cache(self.data)

        class CachedUpdate:
            def __init__(self, **kwargs):
                pass

            def start(self):
                daemon.is_updating = False

        for initial in (None, {"icon_mode": "off", "legacy_field": "preserved"}):
            with self.subTest(initial=initial), contextlib.ExitStack() as stack:
                self.selected_file.unlink(missing_ok=True)
                if initial:
                    state.save_selected(initial)
                output = io.StringIO()
                stack.enter_context(contextlib.redirect_stdout(output))
                stack.enter_context(patch.object(fetch, "check_for_updates"))
                stack.enter_context(patch.object(daemon.threading, "Thread", CachedUpdate))
                stack.enter_context(patch.object(daemon.time, "sleep", side_effect=KeyboardInterrupt))
                stack.enter_context(patch.object(daemon, "is_updating", False))
                stack.enter_context(patch.object(daemon, "should_update", True))
                stack.enter_context(patch.object(daemon, "latest_data", []))
                stack.enter_context(patch.object(daemon, "_results_by_dir", {}))
                stack.enter_context(patch.object(daemon, "_pending", set()))
                for method in ("update_current", "write_tooltip", "signal_waybar"):
                    stack.enter_context(patch.object(daemon.logos, method))
                self.assertEqual(cli.main(["config", "--usage-display", "remaining"]), 0)
                daemon._run("waybar")
                rendered = json.loads(output.getvalue().splitlines()[-1])
                prefix = "" if initial else render.ICON + "\u2003"
                self.assertEqual(rendered["text"], prefix + "Codex (Pro) 0%")
                saved = state.load_selected()
                self.assertEqual(saved["provider"], "codex")
                self.assertEqual(saved["metric"], "weekly")
                self.assertEqual(state.get_usage_display(saved), "remaining")
                if initial:
                    for key, value in initial.items():
                        self.assertEqual(saved[key], value)

    def test_native_partial_loading_and_swiftbar_share_the_same_display(self):
        snapshot = quickshell.build_snapshot(self.data, self.selected, pending={"cursor"})
        self.assertEqual(snapshot["text"], "Codex (Pro) 0%")
        self.assertFalse(snapshot["providers"][0]["loading"])
        self.assertTrue(snapshot["providers"][1]["loading"])
        with patch.object(macos.LogoCache, "get", return_value=""):
            menu = swiftbar.render_menu(self.data, self.selected)
        self.assertEqual(menu.splitlines()[0], "Codex (Pro) 0%")
        self.assertIn("Weekly Remaining:", menu)
        self.assertIn("Other Models included quota remaining:", menu)
        self.assertIn("95%", menu)
        self.assertIn("Reset credits: 3 available", menu)

    def settings_payload(self, **changes):
        return dict(enabled=["codex", "cursor"],
                    display=dict(show_provider=True, show_model=True, show_metric=False, show_pct=True),
                    iconMode="off", selected=dict(provider="codex", idx=0, metric="weekly"), **changes)

    def test_native_settings_persist_and_publish_the_usage_display(self):
        state.save_selected(dict(self.selected, usage_display="used", legacy_field="preserved"))
        with patch.object(state, "trigger_refresh") as refresh:
            quickshell.save_settings(self.settings_payload(usageDisplay="remaining"))
        saved = state.load_selected()
        self.assertEqual(saved["usage_display"], "remaining")
        self.assertEqual(saved["legacy_field"], "preserved")
        self.assertEqual(quickshell.build_snapshot(self.data, saved)["settings"]["usageDisplay"], "remaining")
        refresh.assert_called_once()

    def test_older_native_settings_payload_preserves_saved_mode_and_defaults_to_used(self):
        for initial, expected in (({}, "used"), (self.remaining, "remaining")):
            with self.subTest(initial=initial), patch.object(state, "trigger_refresh"):
                state.save_selected(dict(self.selected, **initial) if initial else {"icon_mode": "off"})
                quickshell.save_settings(self.settings_payload())
                self.assertEqual(state.get_usage_display(state.load_selected()), expected)

    def test_invalid_native_display_mode_never_writes_or_refreshes(self):
        state.save_selected(self.selected)
        before_config, before_selected = self.config_file.read_bytes(), self.selected_file.read_bytes()
        for mode in (None, "invalid", True, 1, [], {}):
            with self.subTest(mode=mode), patch.object(state, "trigger_refresh") as refresh:
                with self.assertRaises(ValueError):
                    quickshell.save_settings(self.settings_payload(usageDisplay=mode))
                self.assertEqual(self.config_file.read_bytes(), before_config)
                self.assertEqual(self.selected_file.read_bytes(), before_selected)
                refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
