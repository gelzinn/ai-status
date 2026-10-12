"""Render production Settings panels offscreen with isolated sample data."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


LIB = Path(__file__).resolve().parents[1]
PROJECT = LIB.parents[1]
SECTIONS = ("general", "appearance", "alerts", "providers")
PROVIDERS = ["codex", "claude", "cursor", "opencode", "copilot", "kiro",
             "openrouter", "anthropic-api", "openai-api", "google-cloud",
             "grok-bot", "commandcode", "deepinfra", "deepseek", "kimi", "minimax"]
NAMES = {"codex": "Codex", "claude": "Claude", "cursor": "Cursor",
         "opencode": "OpenCode", "copilot": "Copilot", "kiro": "Kiro",
         "openrouter": "OpenRouter", "anthropic-api": "Anthropic API",
         "openai-api": "OpenAI API", "google-cloud": "Google Cloud",
         "grok-bot": "Grok Bot", "commandcode": "Command Code",
         "deepinfra": "DeepInfra", "deepseek": "DeepSeek", "kimi": "Kimi", "minimax": "MiniMax"}


def render_quickshell(output):
    runner = os.environ.get("QMLTESTRUNNER") or shutil.which("qmltestrunner")
    if not runner:
        candidate = Path("/usr/lib/qt6/bin/qmltestrunner")
        if candidate.exists():
            runner = str(candidate)
    if not runner:
        raise RuntimeError("Install Qt Quick Test or set QMLTESTRUNNER to its executable.")
    version = json.loads((PROJECT / "package.json").read_text(encoding="utf-8"))["version"]
    with tempfile.TemporaryDirectory(prefix="ai-status-settings-preview-") as directory:
        root = Path(directory)
        for name in ("qs", "Quickshell"):
            shutil.copytree(LIB / "tests/qml" / name, root / name)
        shutil.copytree(LIB / "quickshell", root / "plugin")
        shutil.copy2(LIB / "tests/qml/Model.qml", root / "plugin/Model.qml")
        shutil.copytree(LIB / "assets", root / "assets")
        preview = '''
import QtQuick
import QtTest
import "plugin" as Plugin
Item {
    width: 380
    height: 680
    Plugin.Panel { id: panel; width: 380; height: 680 }
    TestCase {
        name: "SettingsPreviews"
        when: windowShown
        function test_render() {
            Plugin.Model.reset()
            const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
            snapshot.version = {current: VERSION, has_update: false}
            snapshot.settings.order = PROVIDERS
            snapshot.settings.names = NAMES
            snapshot.settings.enabled = PROVIDERS.slice(0, 4)
            snapshot.settings.display = {show_provider: true, show_model: true, show_metric: false, show_pct: true}
            snapshot.settings.iconMode = "logo"
            snapshot.selected = {provider: "codex", idx: 0, metric: "weekly"}
            Plugin.Model.snapshot = snapshot
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            verify(settings !== null)
            for (const section of SECTIONS) {
                settings.selectSection(section)
                wait(150)
                compare(settings.section, section)
                grabImage(findChild(panel, "panel-surface")).save(OUTPUT + "/quickshell-" + section + ".png")
            }
            const scroller = findChild(panel, "panel-scroller")
            scroller.contentY = Math.max(0, scroller.contentHeight - scroller.height)
            wait(150)
            grabImage(findChild(panel, "panel-surface")).save(OUTPUT + "/quickshell-providers-bottom.png")
        }
    }
}
'''
        for token, value in {"VERSION": version, "PROVIDERS": PROVIDERS, "NAMES": NAMES,
                             "SECTIONS": SECTIONS, "OUTPUT": str(output)}.items():
            preview = preview.replace(token, json.dumps(value))
        (root / "tst_Preview.qml").write_text(preview, encoding="utf-8")
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   QML_XHR_ALLOW_FILE_READ="1")
        subprocess.run([runner, "-input", str(root), "-import", str(root)], env=env, check=True)
        for section in (*SECTIONS, "providers-bottom"):
            if not (output / f"quickshell-{section}.png").is_file():
                raise RuntimeError(f"Qt did not save the {section} preview.")


def render_windows(output):
    # The same fixture used by native desktop tests isolates all config/state
    # files, stops collectors/timers and suppresses the system tray.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(LIB / "src"))
    sys.path.insert(0, str(LIB / "tests"))
    from unittest.mock import patch
    from PySide6.QtTest import QTest
    from core import config, paths, state, tray
    from test_tray import DesktopTests

    DesktopTests.setUpClass()
    case = DesktopTests()
    case.setUp()
    try:
        case.app.setStyle("Fusion")
        case.app.setFont(tray.panel_font())
        config.save_config(PROVIDERS[:4])
        state.save_selected({"provider": "codex", "idx": 0, "metric": "weekly",
                             "show_provider": True, "show_model": True,
                             "show_metric": False, "show_pct": True, "icon_mode": "logo"})
        panel = case.dashboard
        panel.selected = state.load_selected()
        panel.data = {
            "codex": [{"provider": "Codex (Plus)", "_idx": 0, "metrics": [
                {"type": "rolling", "percentage": 3, "reset_in_seconds": 15900},
                {"type": "weekly", "percentage": 25, "reset_in_seconds": 561600}]}],
            "claude": [{"provider": "Claude (Max)", "_idx": 0, "metrics": [
                {"type": "rolling", "percentage": 2, "reset_in_seconds": 17700},
                {"type": "weekly", "percentage": 24, "reset_in_seconds": 316800}]}],
        }
        panel.draw()
        with patch.object(paths, "IS_WINDOWS", True), \
             patch.object(tray, "startup_enabled", return_value=False), \
             patch.object(panel, "isActiveWindow", return_value=True):
            panel.show()
            panel.configure()
            for section in SECTIONS:
                panel.settings_view.select_section(section)
                QTest.qWait(150)
                assert panel.grab().save(str(output / f"windows-{section}.png"))
            panel.hide()
    finally:
        case.doCleanups()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("quickshell", "windows", "all"), default="quickshell")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/screenshots/settings-submenus")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.platform in ("quickshell", "all"):
        render_quickshell(output)
    if args.platform in ("windows", "all"):
        render_windows(output)
    print(f"Rendered sample-data Settings previews in {output}")


if __name__ == "__main__":
    main()
