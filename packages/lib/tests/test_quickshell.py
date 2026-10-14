import contextlib
import io
import json
from pathlib import Path
import sys
import selectors
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from core import cli, daemon, fetch, logos, quickshell, render, state

DATA = [
    {"_dir": "claude", "_idx": 0, "provider": "Claude (Pro)", "metrics": [
        {"type": "rolling", "percentage": 25, "reset_in_seconds": 3600},
        {"type": "weekly", "percentage": 62, "detail": "Fable · resets tomorrow"},
        {"type": "weekly", "percentage": 40, "detail": "General · resets tomorrow"},
    ]},
    {"_dir": "codex", "_idx": 0, "provider": "Codex", "_cached": True,
     "_error": "<span>Authentication failed</span>", "metrics": [
         {"type": "rolling", "percentage": 10, "reset_in_seconds": None},
     ]},
]
SELECTED = {"provider": "claude", "idx": 0, "metric": "weekly:Fable", "icon_mode": "off"}


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.order = patch("core.config.enabled_order", return_value=["claude", "codex"])
        self.order.start()
        self.addCleanup(self.order.stop)

    def test_native_metrics_selection_and_plain_details(self):
        snapshot = quickshell.build_snapshot(DATA, SELECTED, pending={"codex"})
        self.assertEqual(snapshot["text"], "Claude (Pro) 62%")
        self.assertEqual(snapshot["selected"]["metric"], "weekly:Fable")
        metrics = snapshot["providers"][0]["metrics"]
        self.assertEqual([m["key"] for m in metrics], ["rolling", "weekly:Fable", "weekly:General"])
        self.assertEqual(metrics[0]["detail"], "Resets in 1h 0m")
        self.assertEqual(snapshot["providers"][1]["error"], "Authentication failed")
        self.assertTrue(snapshot["providers"][1]["cached"])
        self.assertTrue(snapshot["providers"][1]["loading"])
        self.assertNotIn("<span", json.dumps(snapshot))

    def test_missing_provider_and_first_load(self):
        snapshot = quickshell.build_snapshot([], SELECTED, pending={"claude", "codex"})
        self.assertEqual(snapshot["text"], "AI Status …")
        self.assertEqual(snapshot["providers"], [])
        self.assertTrue(snapshot["loading"])
        final = quickshell.build_snapshot([], SELECTED)
        self.assertEqual(final["providers"], [])
        self.assertEqual(final["text"], "AI Status")
        self.assertFalse(final["loading"])

    def test_display_preferences_and_logo_path(self):
        selected = dict(SELECTED, icon_mode="logo", show_provider=False, show_model=False, show_pct=True)
        snapshot = quickshell.build_snapshot(DATA, selected, logo_path="/tmp/provider.svg")
        self.assertEqual(snapshot["text"], "62%")
        self.assertEqual(snapshot["logoPath"], "/tmp/provider.svg")

    def test_panel_logos_are_independent_of_bar_icon_preference(self):
        data = DATA + [dict(DATA[0], _idx=1, provider="Claude (Max)")]
        snapshot = quickshell.build_snapshot(data, SELECTED, logo_paths={"claude": "/tmp/claude.svg", "codex": "/tmp/codex.svg"})
        self.assertEqual(snapshot["iconMode"], "off")
        self.assertEqual(snapshot["logoPath"], "")
        self.assertEqual([p["logoPath"] for p in snapshot["providers"]], ["/tmp/claude.svg", "/tmp/claude.svg", "/tmp/codex.svg"])

    def test_settings_include_disabled_providers_and_display_defaults(self):
        with patch("core.config.available_providers", return_value=["claude", "codex", "kiro"]):
            snapshot = quickshell.build_snapshot(DATA, SELECTED)
        settings = snapshot["settings"]
        self.assertEqual(settings["order"], ["claude", "codex", "kiro"])
        self.assertEqual(settings["enabled"], ["claude", "codex"])
        self.assertEqual(settings["names"], {"claude": "Claude", "codex": "Codex", "kiro": "Kiro"})
        self.assertEqual(settings["display"], dict(show_provider=True, show_model=True, show_metric=False, show_pct=True))

    def test_provider_names_match_shared_catalog_and_about_is_in_snapshot(self):
        snapshot = quickshell.build_snapshot(DATA, SELECTED)
        names = snapshot["settings"]["names"]
        self.assertEqual(names["antigravity"], "Antigravity")
        self.assertEqual(names["commandcode"], "Command Code")
        self.assertEqual(names["opencode"], "OpenCode")
        self.assertEqual(snapshot["about"]["name"], "AI Status")
        self.assertEqual(snapshot["about"]["author"], "gelzin.com")

    def test_non_finite_percentage_is_valid_json(self):
        data = [{"_dir": "claude", "metrics": [{"type": "rolling", "percentage": float("nan")}]}]
        snapshot = quickshell.build_snapshot(data, dict(SELECTED, provider="missing"))
        self.assertEqual(snapshot["providers"], [])
        json.dumps(snapshot, allow_nan=False)

    def test_failed_providers_hidden_but_real_zero_and_cached_success_remain(self):
        data = DATA + [dict(DATA[0], _idx=1, metrics=[]),
                       dict(DATA[0], _idx=2, metrics=[{"type": "generic", "percentage": 0, "detail": "Authentication failed"}]),
                       dict(DATA[0], _idx=4, _error="Temporarily unavailable", metrics=[{"type": "generic", "percentage": 0, "detail": "Temporarily unavailable"}]),
                       dict(DATA[0], _idx=3, metrics=[{"type": "rolling", "percentage": 0, "reset_in_seconds": 3600}])]
        snapshot = quickshell.build_snapshot(data, SELECTED)
        self.assertEqual([(p["id"], p["idx"]) for p in snapshot["providers"]], [("claude", 0), ("claude", 3), ("codex", 0)])
        self.assertEqual(snapshot["providers"][1]["metrics"][0]["percentage"], 0)
        self.assertIn("codex", snapshot["settings"]["enabled"])

    def test_native_metric_click_preserves_preferences_and_does_not_fetch(self):
        with patch.object(state, "load_cache", return_value=DATA), patch.object(state, "load_selected", return_value=SELECTED.copy()), patch.object(state, "save_selected") as save, patch.object(state, "trigger_refresh") as refresh:
            quickshell.select_metric(dict(provider="codex", idx=0, metric="rolling"))
            self.assertEqual(save.call_args.args[0], dict(SELECTED, provider="codex", metric="rolling",
                                                        items=[dict(provider="codex", idx=0, metric="rolling")]))
            with self.assertRaises(ValueError):
                quickshell.select_metric(dict(provider="codex", idx=0, metric="missing"))
            self.assertEqual(save.call_count, 1)
            refresh.assert_not_called()

    def test_default_waybar_output_keeps_pango(self):
        output = render.build_final_state(DATA, SELECTED)
        self.assertEqual(set(output), {"text", "tooltip"})
        self.assertEqual(output["text"], "Claude (Pro) 62%")
        self.assertIn("<span", output["tooltip"])

    def test_native_scroll_does_not_signal_waybar(self):
        with patch.object(state, "load_cache", return_value=DATA), patch.object(state, "load_selected", return_value=SELECTED.copy()), patch.object(state, "save_selected") as save, patch("core.logos.update_current") as logo:
            cli.scroll_down("quickshell")
            self.assertEqual(save.call_args.args[0]["provider"], "codex")
            logo.assert_not_called()
            cli.scroll_down()
            logo.assert_called_once()

    def test_daemon_dispatch_is_backward_compatible(self):
        for arguments, expected in ((["ai-status", "daemon"], "waybar"), (["ai-status", "daemon", "--format", "quickshell"], "quickshell")):
            with patch.object(sys, "argv", arguments), patch.object(sys, "stderr"), patch("builtins.open"), patch.object(daemon, "run") as run:
                cli.main()
                run.assert_called_once_with(output_format=expected)

    def test_selection_changes_during_fetch_and_native_output_has_no_waybar_effects(self):
        selection = SELECTED.copy()

        class PendingThread:
            def __init__(self, **kwargs):
                pass

            def start(self):
                pass

        sleeps = 0

        def advance(seconds):
            nonlocal sleeps
            sleeps += 1
            if sleeps == 1:
                selection.update(provider="codex", metric="rolling")
            elif sleeps == 2:
                daemon._pending.clear()
                daemon.is_updating = False
            else:
                raise KeyboardInterrupt

        output = io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(state, "register_pid"))
            stack.enter_context(patch.object(state, "unregister_pid"))
            stack.enter_context(patch.object(state, "load_cache", return_value=DATA))
            stack.enter_context(patch.object(state, "load_selected", side_effect=lambda: selection.copy()))
            stack.enter_context(patch.object(fetch, "check_for_updates"))
            cache = stack.enter_context(patch.object(quickshell.LogoCache, "get", side_effect=lambda name: "/tmp/" + name + ".svg"))
            stack.enter_context(patch.object(daemon.threading, "Thread", PendingThread))
            stack.enter_context(patch.object(daemon.time, "sleep", side_effect=advance))
            logo = stack.enter_context(patch.object(daemon.logos, "update_current"))
            signal = stack.enter_context(patch.object(daemon.logos, "signal_waybar"))
            tooltip = stack.enter_context(patch.object(daemon.logos, "write_tooltip"))
            stack.enter_context(contextlib.redirect_stdout(output))
            daemon.run("quickshell")
            logo.assert_not_called()
            signal.assert_not_called()
            tooltip.assert_not_called()
            self.assertTrue(any(call.args == ("codex",) for call in cache.call_args_list))
        snapshots = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertTrue(all(s["schemaVersion"] == 1 for s in snapshots))
        self.assertTrue(any(s["loading"] and s["selected"]["provider"] == "codex" for s in snapshots))
        self.assertFalse(snapshots[-1]["loading"])

    def test_cached_logo_does_not_download_or_flatten(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = quickshell.LogoCache()
            cache.directory = Path(directory)
            path = cache.directory / "claude.svg"
            path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            with patch.object(quickshell.urllib.request, "urlopen") as network:
                self.assertEqual(cache.get("claude"), str(path))
                network.assert_not_called()

    def test_dark_provider_marks_override_old_remote_caches_without_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = quickshell.LogoCache()
            cache.directory = Path(directory)
            for provider in ("kilo", "lyceum"):
                with self.subTest(provider=provider):
                    (cache.directory / f"{provider}.png").write_bytes(b"old dark remote favicon")
                    expected = str(quickshell.paths.LIB_DIR / "assets" / "providers" / f"{provider}.png")
                    with patch.object(quickshell.threading, "Thread") as download, \
                         patch.object(logos, "request_bytes") as request, \
                         patch.object(logos, "CACHE_DIR", str(cache.directory / "waybar")):
                        self.assertEqual(cache.get(provider), expected)
                        self.assertEqual(logos.provider_png(provider), expected)
                        self.assertTrue(Path(logos.CACHE_DIR).is_dir())
                        # Waybar requires opaque RGB rather than alpha or grayscale.
                        self.assertEqual(Path(expected).read_bytes()[25], 2)
                        download.assert_not_called()
                        request.assert_not_called()

    def test_errors_are_exposed_only_when_requested(self):
        with patch.object(fetch, "run_provider", return_value={"error": "Authentication failed"}):
            self.assertEqual(fetch.fetch_all_data(), [])
            data = fetch.fetch_all_data(include_errors=True)
            self.assertEqual(len(data), 2)
            self.assertEqual(data[0]["_error"], "Authentication failed")

    def test_manifest_entry_and_version(self):
        root = Path(__file__).resolve().parents[3]
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertTrue((root / manifest["entryPoints"]["barWidget"]).is_file())
        self.assertEqual(manifest["version"], json.loads((root / "package.json").read_text())["version"])

    def test_unavailable_selection_does_not_report_zero_usage(self):
        data = DATA[1:] + [{"_dir": "claude", "_idx": 0, "provider": "Claude", "metrics": [], "_error": "Authentication failed"}]
        snapshot = quickshell.build_snapshot(data, SELECTED)
        self.assertEqual(snapshot["text"], "Codex 10%")
        self.assertEqual(snapshot["selected"]["provider"], "codex")
        self.assertEqual(len(snapshot["providers"]), 1)

    def test_native_scroll_skips_failed_providers(self):
        data = [dict(DATA[0], metrics=[]), DATA[1]]
        with patch.object(state, "load_cache", return_value=data), patch.object(state, "load_selected", return_value=SELECTED.copy()), patch.object(state, "save_selected") as save:
            cli.scroll_down("quickshell")
            self.assertEqual(save.call_args.args[0]["provider"], "codex")
        with patch.object(state, "load_cache", return_value=[]), patch.object(state, "save_selected") as save:
            cli.scroll_down("quickshell")
            save.assert_not_called()

    def test_streamed_metrics_are_selectable_before_all_queries_finish(self):
        saved_cache = []

        def query(on_result=None, include_errors=False, check_updates=False):
            self.assertTrue(check_updates)
            on_result("claude", DATA[:1])
            self.assertEqual(saved_cache, DATA[:1])
            self.assertNotIn("claude", daemon._pending)
            self.assertIn("codex", daemon._pending)
            return DATA

        daemon._results_by_dir = {}
        daemon._pending = {"claude", "codex"}
        with patch.object(state, "acquire_lock", return_value=True), patch.object(state, "release_lock"), patch.object(state, "save_cache", side_effect=lambda data: saved_cache.__setitem__(slice(None), data)), patch.object(fetch, "fetch_all_data", side_effect=query):
            daemon.update_task("quickshell")
        self.assertEqual(saved_cache, DATA)

    @unittest.skipIf(sys.platform == "win32", "Requires Unix PID signaling and pipe selectors")
    def test_unregister_keeps_other_frontends_refresh_targets(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(state, "PID_FILE", str(Path(directory) / "pids")), patch.object(state.os, "kill"):
            with patch.object(state.os, "getpid", return_value=101):
                state.register_pid()
            with patch.object(state.os, "getpid", return_value=202):
                state.register_pid()
            with patch.object(state.os, "getpid", return_value=101):
                state.unregister_pid()
            self.assertEqual(Path(state.PID_FILE).read_text(), "202\n")

    def test_disabled_selection_falls_back_to_an_enabled_provider(self):
        with patch("core.config.enabled_order", return_value=["codex"]):
            snapshot = quickshell.build_snapshot(DATA, SELECTED)
        self.assertEqual(snapshot["selected"]["provider"], "codex")
        self.assertEqual(snapshot["text"], "Codex 10%")
        self.assertEqual(SELECTED["provider"], "claude")

    @unittest.skipIf(sys.platform == "win32", "Requires Unix PID signaling and pipe selectors")
    def test_real_daemon_stream_and_termination(self):
        # Run the actual CLI/loop in a subprocess, with fake queries and fully
        # isolated state; catches buffering, serialization, and SIGTERM errors.
        with tempfile.TemporaryDirectory() as directory:
            source = str(Path(__file__).resolve().parents[1] / "src")
            script = '''
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
from core import cli, config, fetch, quickshell, state
directory = pathlib.Path(sys.argv[2])
state.PID_FILE = str(directory / 'pids')
state.LOCK_FILE = str(directory / 'query-lock')
state.CACHE_FILE = str(directory / 'cache')
state.SELECTED_FILE = str(directory / 'selected')
config.CONFIG_FILE = str(directory / 'providers')
config.enabled_order = lambda: ['claude']
data = json.loads(sys.argv[3])
state.save_cache(data)
state.save_selected(json.loads(sys.argv[4]))
fetch.check_for_updates = lambda: None
quickshell.LogoCache.get = lambda self, provider: ''
def query(on_result=None, include_errors=False):
    if on_result: on_result('claude', data)
    return data
fetch.fetch_all_data = query
sys.argv = ['ai-status', 'daemon', '--format', 'quickshell']
cli.main()
'''
            process = subprocess.Popen([sys.executable, "-u", "-c", script, source, directory, json.dumps(DATA[:1]), json.dumps(dict(SELECTED, metric="missing"))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.addCleanup(lambda: process.kill() if process.poll() is None else None)
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)
            self.addCleanup(selector.close)
            self.assertTrue(selector.select(timeout=5), "daemon emitted no snapshot")
            initial = json.loads(process.stdout.readline())
            self.assertEqual(initial["schemaVersion"], 1)
            self.assertEqual(initial["selected"]["provider"], "claude")
            self.assertEqual(initial["selected"]["metric"], "rolling")
            self.assertEqual(json.loads((Path(directory) / "selected").read_text())["metric"], "rolling")
            process.terminate()
            output, errors = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, errors)
            self.assertNotIn(str(process.pid), (Path(directory) / "pids").read_text())


class NativeSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config_file = Path(temporary.name) / "config/providers.json"
        self.selected_file = Path(temporary.name) / "config/selected.json"
        for replacement in (
            patch("core.config.CONFIG_FILE", str(self.config_file)),
            patch("core.state.SELECTED_FILE", str(self.selected_file)),
            patch("core.config.available_providers", return_value=["claude", "codex"]),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)
        refresh_patch = patch.object(state, "trigger_refresh")
        self.refresh = refresh_patch.start()
        self.addCleanup(refresh_patch.stop)
        self.payload = {
            "enabled": ["codex", "claude"],
            "display": dict(show_provider=True, show_model=False, show_metric=True, show_pct=True),
            "iconMode": "logo",
            "selected": dict(provider="claude", idx=0, metric="weekly:Fable"),
        }

    def test_native_save_persists_order_selection_and_display_without_waybar_side_effects(self):
        state._save_json(str(self.selected_file), dict(SELECTED, legacy_field="preserved"))
        with patch("core.logos.update_current") as logo, patch("core.logos.signal_waybar") as signal:
            quickshell.save_settings(self.payload)
            logo.assert_not_called()
            signal.assert_not_called()
        self.assertEqual(json.loads(self.config_file.read_text()), ["codex", "claude"])
        selected = json.loads(self.selected_file.read_text())
        self.assertEqual(selected["metric"], "weekly:Fable")
        self.assertEqual(selected["legacy_field"], "preserved")
        self.assertFalse(selected["show_model"])
        self.assertEqual(selected["icon_mode"], "logo")
        self.refresh.assert_called_once()

    def test_provider_order_roundtrip_drives_bar_pins_and_keeps_unavailable_limits(self):
        unavailable = dict(provider="claude", idx=0, metric="weekly:unavailable")
        items = [dict(provider="claude", idx=0, metric="weekly:Fable"),
                 dict(provider="codex", idx=0, metric="rolling"),
                 unavailable, dict(provider="claude", idx=0, metric="rolling")]
        for provider_order, expected in (
                (["codex", "claude"], [items[1], items[0], unavailable, items[3]]),
                (["claude", "codex"], [items[0], unavailable, items[3], items[1]])):
            with self.subTest(order=provider_order):
                quickshell.save_settings(dict(self.payload, enabled=provider_order, items=items))
                saved = state.load_selected()
                self.assertEqual(json.loads(self.config_file.read_text()), provider_order)
                self.assertEqual(state.get_selected_items(saved), expected)
                self.assertEqual({key: saved[key] for key in ("provider", "idx", "metric")}, expected[0])
                snapshot = quickshell.build_snapshot(DATA, saved)
                self.assertEqual(snapshot["settings"]["items"], expected)
                self.assertEqual(snapshot["settings"]["enabled"], provider_order)
                self.assertEqual([{key: item[key] for key in ("provider", "idx", "metric")}
                                  for item in snapshot["barItems"]],
                                 [item for item in expected if item != unavailable])

    def test_invalid_settings_do_not_write_or_refresh(self):
        invalid = [None, [], {},
            dict(self.payload, enabled=[]),
            dict(self.payload, enabled=["claude", "claude"]),
            dict(self.payload, enabled=["unknown"]),
            dict(self.payload, enabled=[{}]),
            dict(self.payload, display=dict.fromkeys(self.payload["display"], False)),
            dict(self.payload, display=dict(self.payload["display"], show_pct="yes")),
            dict(self.payload, iconMode="invalid"),
            dict(self.payload, selected=dict(provider="disabled", idx=0, metric="rolling")),
            dict(self.payload, selected=dict(provider="claude", idx=-1, metric="rolling")),
            dict(self.payload, selected=dict(provider="claude", idx=0, metric="")),
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                quickshell.save_settings(payload)
            self.assertFalse(self.config_file.exists())
            self.assertFalse(self.selected_file.exists())
        self.refresh.assert_not_called()

    def test_cli_reports_save_validation_and_disk_errors(self):
        for payload, error in (({}, None), (self.payload, OSError("Disk full"))):
            with patch.object(sys, "argv", ["ai-status", "save-settings", "--frontend", "quickshell", "--settings-json", json.dumps(payload)]), patch.object(sys, "stderr", io.StringIO()) as stderr, patch.object(state, "_save_json", side_effect=error):
                self.assertEqual(cli.main(), 1)
                self.assertTrue(stderr.getvalue().strip())
        self.refresh.assert_not_called()

    @unittest.skipIf(sys.platform == "win32", "Windows configuration uses the tray dialog")
    def test_waybar_config_retains_terminal_tui(self):
        with patch.object(sys, "argv", ["ai-status", "config"]), patch.object(sys.stdout, "isatty", return_value=True), patch("core.tui.run") as tui:
            cli.main()
            tui.assert_called_once()


if __name__ == "__main__":
    unittest.main()
