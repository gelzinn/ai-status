"""Render the production Windows widgets with sample update events, offline.

Use --before-ref to render an earlier Git revision with the identical fixture.
The native macOS smoke runner and QML preview supply the other platform images.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtTest import QTest
from core import fetch, paths, tray, updates
import test_tray


def reject_update(*args, **kwargs):
    raise AssertionError("Previews must never download or install an update")


SAMPLE_RELEASE_NOTES = {
    "version": "0.16.0", "title": "v0.16.0",
    "url": "https://github.com/gelzinn/ai-status/releases/tag/v0.16.0",
    "body": "### Features\n- Show live download progress with transferred and remaining bytes.\n"
            "- Keep update actions and error feedback consistent across desktop panels.\n\n"
            "### Fixes\n- Preserve settings and provider connections during updates.\n"
            "- Keep the updater running when the old app closes.",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--before-ref", help="Render this Git revision's update widgets and guide")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    adapter, guide_module = tray, updates
    with tempfile.TemporaryDirectory(prefix="ai-status-update-preview-") as temporary:
        if args.before_ref:
            for name in ("updates", "tray"):
                source = subprocess.check_output([
                    "git", "show", args.before_ref + ":packages/lib/src/core/" + name + ".py"])
                filename = Path(temporary) / (name + ".py")
                filename.write_bytes(source)
                spec = importlib.util.spec_from_file_location("core.preview_" + name, filename)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if name == "updates":
                    guide_module = module
                else:
                    adapter = module
                    adapter.updates = guide_module
            test_tray.tray = adapter

        test_tray.DesktopTests.setUpClass()
        test = test_tray.DesktopTests()
        test.setUp()
        dashboard = test.dashboard
        try:
            with patch.object(adapter, "__version__", "0.15.0"), \
                    patch.object(fetch, "__version__", "0.15.0"), \
                    patch.object(fetch, "_latest_version", "0.16.0"), \
                    patch.object(fetch, "_latest_release_notes", SAMPLE_RELEASE_NOTES), \
                    patch.object(guide_module, "_installation", return_value=("windows-installer", {})), \
                    patch.object(guide_module, "run_update", side_effect=reject_update), \
                    patch.object(fetch, "check_for_updates", side_effect=reject_update):
                dashboard.version.setText("v0.15.0")
                view = dashboard.update_view

                def capture(name):
                    dashboard.fit_content()
                    test.app.processEvents()
                    QTest.mouseMove(dashboard, adapter.QPoint(dashboard.width() - 8, 8))
                    QTest.qWait(150)
                    filename = args.output / (name + ".png")
                    if not dashboard.grab().save(str(filename)):
                        raise RuntimeError("Could not save " + str(filename))
                    print(filename)

                dashboard.on_result("codex", [{"provider": "Codex (Pro)", "metrics": [
                    {"type": "weekly", "percentage": 23, "reset_in_seconds": 583200}]}])
                dashboard.show_dashboard()
                capture("windows-available")
                dashboard.show_updates()
                capture("windows-guide")
                view.running = True
                view.update_action()
                if args.before_ref:
                    view.show_progress("Downloading the Windows installer…")
                else:
                    view.show_progress({"stage": "checking", "message": "Checking the latest stable release…"})
                    capture("windows-checking")
                    view.show_progress({"stage": "checking", "message": "Checking the release checksum…"})
                    capture("windows-checksum")
                    view.show_progress({"stage": "downloading", "message": "Downloading the Windows installer…",
                                        "downloadedBytes": 2_520_000})
                    capture("windows-downloading-unknown")
                    view.show_progress({"stage": "downloading", "message": "Downloading the Windows installer…",
                                        "downloadedBytes": 7_560_000, "totalBytes": 18_000_000, "percent": 42})
                capture("windows-downloading")
                if not args.before_ref:
                    view.show_progress({"stage": "verifying", "message": "Verifying the installer…"})
                    capture("windows-verifying")
                    view.show_progress({"stage": "opening", "message": "Opening setup automatically…"})
                    capture("windows-opening")
                    dashboard.on_update_finished(
                        "Setup is open. Finish installation and leave Launch AI Status selected to reopen the app.", True)
                    capture("windows-installer")
                    view.set_guide(guide_module.update_guide(), fetch.get_version_info())
                    dashboard.on_update_finished("Download failed. Check your connection and retry.", False)
                    capture("windows-error")
                    view.running = True
                    view.failed = False
                    view.completed = False
                    view.update_action()
                    view.show_progress({"stage": "checking", "message": "Checking the latest stable release…"})
                    capture("windows-retry")
                    with patch.object(fetch, "_latest_version", "0.15.0"):
                        view.set_guide(guide_module.update_guide(), fetch.get_version_info())
                        dashboard.on_update_finished("AI Status is already up to date.", True)
                        capture("windows-up-to-date")
                    with patch.object(fetch, "__version__", "0.16.0"), \
                            patch.object(fetch, "get_version_info", return_value={
                                "current": "0.16.0", "latest": "0.16.0", "has_update": False}):
                        dashboard.version.setText("v0.16.0")
                        view.completed = False
                        view.status.clear()
                        dashboard.draw()
                        dashboard.show_usage()
                        capture("windows-reopened")
        finally:
            test.doCleanups()


if __name__ == "__main__":
    main()
