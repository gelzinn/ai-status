"""Ordered shared bar preferences survive migration, refreshes and native saves."""

import copy
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, config, daemon, quickshell, render, state, swiftbar


CLAUDE = dict(provider="claude", idx=0, metric="rolling")
WEEKLY = dict(provider="claude", idx=0, metric="weekly")
CODEX = dict(provider="codex", idx=1, metric="weekly")
DATA = [
    dict(_dir="claude", _idx=0, provider="Claude", metrics=[
        dict(type="rolling", percentage=25), dict(type="weekly", percentage=50)]),
    dict(_dir="codex", _idx=1, provider="Codex", metrics=[dict(type="weekly", percentage=10)]),
]


class BarItemsTests(unittest.TestCase):
    def setUp(self):
        for replacement in (
            patch.object(config, "enabled_connection_order", return_value=["claude", "codex"]),
            patch.object(config, "available_connections", return_value=["claude", "codex"]),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)

    def selected(self, items, **preferences):
        return state.set_selected_items(dict(icon_mode="off", **preferences), items)

    def test_legacy_singleton_migrates_without_losing_display_or_custom_preferences(self):
        legacy = dict(CLAUDE, usage_display="remaining", custom={"keep": True})
        self.assertEqual(state.get_selected_items(legacy), [CLAUDE])
        updated = state.select_primary(legacy, WEEKLY)
        self.assertIs(updated, legacy)
        self.assertEqual(updated["items"], [WEEKLY])
        self.assertEqual(updated["custom"], {"keep": True})
        self.assertEqual(updated["usage_display"], "remaining")
        self.assertEqual(updated["metric"], "weekly")

    def test_normalization_deduplicates_identity_and_rejects_bad_indices(self):
        items = [CLAUDE, WEEKLY, CLAUDE, CODEX, dict(CODEX, idx=True), dict(CODEX, idx=-1), None]
        self.assertEqual(state.get_selected_items({"items": items}), [CLAUDE, WEEKLY, CODEX])
        other_account = dict(CODEX, provider="account:work")
        self.assertEqual(state.get_selected_items({"items": [CODEX, other_account]}), [CODEX, other_account])

    def test_provider_order_preserves_account_metric_identity_and_unknown_groups(self):
        other_account = dict(CODEX, provider="account:work", idx=3)
        unavailable = dict(WEEKLY, metric="weekly:unavailable")
        orphan = dict(CODEX, provider="account:deleted", idx=5)
        other_orphan = dict(CLAUDE, provider="retired")
        items = [orphan, WEEKLY, CODEX, unavailable, other_account, CLAUDE,
                 other_orphan, dict(CODEX, label="ignored"), None]
        before = copy.deepcopy(items)
        self.assertEqual(state.order_bar_items(items, ["codex", "account:work", "claude"]),
                         [CODEX, other_account, WEEKLY, unavailable, CLAUDE, orphan, other_orphan])
        self.assertEqual(state.order_bar_items(items, ["claude", "codex", "account:work"]),
                         [WEEKLY, unavailable, CLAUDE, CODEX, other_account, orphan, other_orphan])
        self.assertEqual(items, before)

    def test_primary_replacement_preserves_other_slots_and_deduplicates(self):
        selected = self.selected([CLAUDE, CODEX, WEEKLY])
        state.select_primary(selected, CODEX)
        self.assertEqual(selected["items"], [CODEX, WEEKLY])
        self.assertEqual(selected["provider"], "codex")
        self.assertEqual(selected["idx"], 1)

    def test_snapshot_respects_item_order_and_per_item_logo_and_loading(self):
        selected = self.selected([CODEX, WEEKLY, CLAUDE])
        selected["icon_mode"] = "logo"
        snapshot = quickshell.build_snapshot(DATA, selected, pending={"claude"},
                                             logo_paths={"claude": "/tmp/claude.png", "codex": "/tmp/codex.png"})
        self.assertEqual([(item["provider"], item["metric"]) for item in snapshot["barItems"]],
                         [("codex", "weekly"), ("claude", "weekly"), ("claude", "rolling")])
        self.assertEqual([item["loading"] for item in snapshot["barItems"]], [False, True, True])
        self.assertEqual([item["logoPath"] for item in snapshot["barItems"]],
                         ["/tmp/codex.png", "/tmp/claude.png", "/tmp/claude.png"])
        self.assertEqual(snapshot["text"], "Codex 10% · Claude … · Claude …")
        self.assertEqual(snapshot["settings"]["items"], selected["items"])
        self.assertEqual(snapshot["selected"]["provider"], "codex")

    def test_missing_pins_do_not_duplicate_fallback_or_destroy_configuration(self):
        selected = self.selected([dict(WEEKLY, metric="monthly"), CODEX, CLAUDE])
        before = copy.deepcopy(selected)
        snapshot = quickshell.build_snapshot(DATA, selected)
        self.assertEqual(snapshot["text"], "Codex 10% · Claude 25%")
        self.assertEqual(snapshot["settings"]["items"], before["items"])
        self.assertEqual(selected, before)
        restored = copy.deepcopy(DATA)
        restored[0]["metrics"].append(dict(type="monthly", percentage=70))
        self.assertEqual(quickshell.build_snapshot(restored, selected)["text"], "Claude 70% · Codex 10% · Claude 25%")

    def test_all_missing_explicit_pins_show_generic_status_while_legacy_falls_back(self):
        selected = self.selected([dict(CLAUDE, metric="missing")])
        snapshot = quickshell.build_snapshot(DATA, selected)
        self.assertEqual(snapshot["barItems"], [])
        self.assertEqual(snapshot["text"], "AI Status")
        self.assertEqual(snapshot["settings"]["items"], selected["items"])
        self.assertEqual(render.build_final_state(DATA, selected)["text"], "AI Status")
        legacy = dict(CLAUDE, provider="missing", icon_mode="off")
        legacy_snapshot = quickshell.build_snapshot(DATA, legacy)
        self.assertEqual(legacy_snapshot["text"], "Claude 25%")
        self.assertEqual(legacy_snapshot["settings"]["items"], [CLAUDE])

    def test_waybar_stream_loads_each_selected_connection_independently(self):
        selected = self.selected([CLAUDE, CODEX, WEEKLY], usage_display="remaining")
        output = render.build_loading_state(DATA, 0, selected, pending={"codex"})
        self.assertEqual(output["text"], "Claude 75% · Codex " + render.SPINNERS[0] + " · Claude 50%")
        self.assertEqual(render.build_final_state(DATA, selected)["text"], "Claude 75% · Codex 90% · Claude 50%")

    def test_metric_click_and_cycle_keep_extra_pins(self):
        for action in (lambda: quickshell.select_metric(WEEKLY), lambda: cli.cycle_metric("quickshell")):
            with self.subTest(action=action), patch.object(state, "load_cache", return_value=DATA), \
                    patch.object(state, "load_selected", return_value=self.selected([CLAUDE, CODEX])), \
                    patch.object(state, "save_selected") as save:
                action()
                self.assertEqual(save.call_args.args[0]["items"], [WEEKLY, CODEX])

    def test_click_scroll_and_cycle_keep_the_shared_provider_order(self):
        for action in (lambda: quickshell.select_metric(CODEX),
                       lambda: cli.scroll_down("quickshell"),
                       lambda: cli.cycle_metric("quickshell")):
            with self.subTest(action=action), patch.object(state, "load_cache", return_value=DATA), \
                    patch.object(state, "load_selected", return_value=self.selected([CLAUDE, CODEX, WEEKLY])), \
                    patch.object(state, "save_selected") as save:
                action()
                saved = save.call_args.args[0]
                self.assertEqual(saved["items"], [WEEKLY, CODEX])
                self.assertEqual({key: saved[key] for key in ("provider", "idx", "metric")}, WEEKLY)

    def test_swiftbar_title_and_checks_include_every_selected_item(self):
        selected = self.selected([CODEX, WEEKLY, CLAUDE])
        with patch.object(swiftbar.macos.LogoCache, "get", return_value=""):
            menu = swiftbar.render_menu(DATA, selected)
        self.assertEqual(menu.splitlines()[0], "Codex 10% · Claude 50% · Claude 25%")
        self.assertEqual(menu.count("checked=true"), 3)

    def test_waybar_refresh_updates_logo_to_first_visible_item_without_saving_pins(self):
        selected = self.selected([CLAUDE, CODEX])
        selected["icon_mode"] = "logo"
        sleeps = 0

        def advance(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 1:
                daemon._results_by_dir["claude"] = DATA[:1]
                daemon._pending.discard("claude")
            elif sleeps == 2:
                daemon.latest_data = DATA
                daemon.is_updating = False
            else:
                raise KeyboardInterrupt

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            for name, value in (("should_update", True), ("is_updating", False), ("latest_data", []),
                                ("_results_by_dir", {}), ("_pending", set())):
                stack.enter_context(patch.object(daemon, name, value))
            stack.enter_context(patch.object(state, "load_cache", return_value=DATA[1:]))
            stack.enter_context(patch.object(state, "load_selected", side_effect=lambda: copy.deepcopy(selected)))
            save = stack.enter_context(patch.object(state, "save_selected"))
            stack.enter_context(patch.object(daemon.threading, "Thread"))
            stack.enter_context(patch.object(daemon.time, "sleep", side_effect=advance))
            stack.enter_context(patch.object(daemon.logos, "write_tooltip"))
            stack.enter_context(patch.object(daemon.logos, "signal_waybar"))
            stack.enter_context(patch.object(daemon.notifications, "next_check_delay", return_value=300))
            logo = stack.enter_context(patch.object(daemon.logos, "update_current"))
            stack.enter_context(contextlib.redirect_stdout(output))
            daemon._run("waybar")
            self.assertEqual([call.args[0]["provider"] for call in logo.call_args_list], ["codex", "claude"])
            save.assert_not_called()
        emitted = [json.loads(line)["text"] for line in output.getvalue().splitlines()]
        self.assertEqual(emitted[0], "Codex " + render.SPINNERS[0])
        self.assertTrue(emitted[1].startswith("Claude 25% · Codex "))
        self.assertEqual(selected["items"], [CLAUDE, CODEX])

    def test_waybar_logo_hides_when_every_explicit_pin_is_unavailable(self):
        selected = self.selected([dict(CLAUDE, metric="missing")])
        selected["icon_mode"] = "logo"
        with patch.object(state, "load_cache", return_value=DATA), \
                patch.object(state, "load_selected", return_value=selected), \
                patch.object(daemon.logos, "update_current") as logo, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            cli.print_logo()
        self.assertEqual(output.getvalue(), "\n")
        logo.assert_not_called()


class BarItemsSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "selected.json"
        for replacement in (
            patch.object(state, "SELECTED_FILE", str(self.path)),
            patch.object(config, "available_connections", return_value=["claude", "codex"]),
            patch.object(config, "save_connection_order"),
            patch.object(state, "trigger_refresh"),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        self.payload = dict(enabled=["claude", "codex"], iconMode="off",
                            display=dict(show_provider=True, show_model=False, show_metric=False, show_pct=True))

    def test_items_only_form_saves_arbitrary_count_in_order_and_mirrors_first(self):
        items = [dict(CLAUDE, metric=f"weekly:limit-{index}") for index in range(25)]
        quickshell.save_settings(dict(self.payload, items=items))
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["items"], items)
        self.assertEqual(saved["metric"], "weekly:limit-0")

    def test_legacy_form_retains_enabled_extra_pins_and_custom_preferences(self):
        state.save_selected(state.set_selected_items({"custom": "preserved"}, [CLAUDE, CODEX]))
        quickshell.save_settings(dict(self.payload, selected=WEEKLY))
        saved = state.load_selected()
        self.assertEqual(saved["items"], [WEEKLY, CODEX])
        self.assertEqual(saved["custom"], "preserved")
        quickshell.save_settings(dict(self.payload, enabled=["claude"], selected=CLAUDE))
        self.assertEqual(state.load_selected()["items"], [CLAUDE])

    def test_invalid_lists_do_not_partially_publish_preferences(self):
        for items in ([], None, {}, [CLAUDE, CLAUDE], [dict(CLAUDE, idx=True)],
                      [dict(CLAUDE, idx=-1)], [dict(CLAUDE, metric="")],
                      [dict(CLAUDE, provider="disabled")], [dict(metric="weekly", idx=0)]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                quickshell.save_settings(dict(self.payload, items=items))
            self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
