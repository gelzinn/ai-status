"""Capture production Quickshell settings and bar items with isolated sample usage."""

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch


LIB = Path(__file__).resolve().parents[1]
PROJECT = LIB.parents[1]
ITEMS = [
    {"provider": "codex", "idx": 0, "metric": "weekly"},
    {"provider": "claude", "idx": 0, "metric": "rolling"},
    {"provider": "claude", "idx": 0, "metric": "weekly"},
]
SELECTED = {
    **ITEMS[0], "items": copy.deepcopy(ITEMS), "icon_mode": "logo", "usage_display": "used",
    "show_provider": True, "show_model": True, "show_metric": True, "show_pct": True,
    "refresh_interval_minutes": 5,
}
DATA = [
    {"_dir": "codex", "_idx": 0, "provider": "Codex (Plus)", "metrics": [
        {"type": "rolling", "percentage": 13, "reset_in_seconds": 12600},
        {"type": "weekly", "percentage": 27, "reset_in_seconds": 345600},
    ]},
    {"_dir": "claude", "_idx": 0, "provider": "Claude (Max)", "metrics": [
        {"type": "rolling", "percentage": 45, "reset_in_seconds": 7200},
        {"type": "weekly", "percentage": 62, "reset_in_seconds": 172800},
        {"type": "weekly", "percentage": 38, "detail": "Fable · Resets in 2d"},
    ]},
]


def fixture_snapshot():
    """Build the real shared desktop model without reading account preferences."""
    sys.path.insert(0, str(LIB / "src"))
    from core import config, fetch, notifications, quickshell

    version = json.loads((PROJECT / "package.json").read_text(encoding="utf-8"))["version"]
    logos = {name: str(LIB / "assets/providers" / f"{name}.png") for name in ("codex", "claude")}
    with patch.object(config, "available_connections", return_value=["codex", "claude", "kiro"]), \
            patch.object(config, "enabled_connection_order", return_value=["codex", "claude"]), \
            patch.object(config, "connection_info", side_effect=lambda name: {"provider": name, "label": ""}), \
            patch.object(notifications, "load_settings", return_value=copy.deepcopy(notifications.DEFAULT_SETTINGS)), \
            patch.object(fetch, "get_version_info", return_value={"current": version, "latest": version, "has_update": False}):
        return quickshell.build_snapshot(copy.deepcopy(DATA), copy.deepcopy(SELECTED), logo_paths=logos)


def render_linux(output, renderer="software"):
    runner = os.environ.get("QMLTESTRUNNER") or shutil.which("qmltestrunner")
    if not runner and Path("/usr/lib/qt6/bin/qmltestrunner").is_file():
        runner = "/usr/lib/qt6/bin/qmltestrunner"
    if not runner:
        raise RuntimeError("Install Qt Quick Test or set QMLTESTRUNNER.")

    for name in ("linux-settings.png", "linux-bar.png"):
        (output / name).unlink(missing_ok=True)

    snapshot = fixture_snapshot()
    with tempfile.TemporaryDirectory(prefix="ai-status-bar-items-preview-") as directory:
        root = Path(directory)
        for name in ("qs", "Quickshell"):
            shutil.copytree(LIB / "tests/qml" / name, root / name)
        shutil.copytree(LIB / "quickshell", root / "plugin")
        shutil.copy2(LIB / "tests/qml/Model.qml", root / "plugin/Model.qml")
        shutil.copytree(LIB / "assets", root / "assets")
        preview = '''
import QtQuick
import QtTest
import qs.Commons
import "plugin" as Plugin

Item {
    id: scene
    width: 1280
    height: 720
    property bool barPreview: false
    property var captureSnapshot: SNAPSHOT_DATA
    QtObject { id: shell; property string fontFamily: Style.font.family }
    Plugin.Panel { id: panel; width: 380; height: 680; visible: !scene.barPreview }
    Rectangle {
        id: strip
        visible: scene.barPreview
        width: widget.implicitWidth + clock.implicitWidth + 80
        height: 52
        color: "#111111"
        border.color: "#282828"
        Plugin.BarWidget {
            id: widget
            x: 16
            anchors.verticalCenter: parent.verticalCenter
            bar: shell
            barSize: 40
        }
        Text {
            id: clock
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            text: "14:32"
            color: "#eeeeee"
            font.family: Style.font.family
            font.pixelSize: Style.font.body
        }
    }
    TestCase {
        name: "MultipleBarItemsPreviews"
        when: windowShown
        function test_capture() {
            Plugin.Model.reset()
            Plugin.Model.snapshot = scene.captureSnapshot
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            const scroller = findChild(panel, "panel-scroller")
            compare(settings.section, "general")
            compare(settings.selectedItems.length, 3)
            compare(settings.refreshIntervalMinutes, 5)
            for (const item of scene.captureSnapshot.settings.items) {
                const row = findChild(settings, "bar-item-" + item.provider + "-" + item.idx + "-" + item.metric)
                verify(row !== null && row.checked)
            }
            verify(!findChild(settings, "bar-item-codex-0-rolling").checked)
            verify(!findChild(settings, "bar-item-claude-0-weekly:Fable").checked)
            scroller.contentY = 0
            wait(250)
            const settingsImage = grabImage(findChild(panel, "panel-surface"))
            verify(settingsImage.width > 0 && settingsImage.height > 0)
            settingsImage.save(OUTPUT + "/linux-settings.png")

            scene.barPreview = true
            wait(250)
            for (let index = 0; index < 3; index++) {
                const label = findChild(widget, "bar-item-label-" + index)
                const logo = findChild(widget, "bar-item-logo-" + index)
                compare(label.text, scene.captureSnapshot.barItems[index].text)
                tryCompare(logo, "status", Image.Ready)
                verify(logo.visible, "Bar logo " + index + " must be visible")
            }
            wait(250)
            const barImage = grabImage(strip)
            verify(barImage.width > 0 && barImage.height > 0)
            barImage.save(OUTPUT + "/linux-bar.png")
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)
            console.info("CAPTURE_FILES linux-settings.png linux-bar.png")
        }
    }
}
'''
        preview = preview.replace("SNAPSHOT_DATA", json.dumps(snapshot)).replace("OUTPUT", json.dumps(str(output)))
        (root / "tst_Preview.qml").write_text(preview, encoding="utf-8")
        env = dict(os.environ, QML_XHR_ALLOW_FILE_READ="1")
        if renderer == "opengl":
            env.update(QT_QPA_PLATFORM="xcb", QSG_RHI_BACKEND="opengl", LIBGL_ALWAYS_SOFTWARE="1")
            env.pop("QT_QUICK_BACKEND", None)
        else:
            env.update(QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        result = subprocess.run([runner, "-input", str(root), "-import", str(root)], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print(result.stdout, end="")
        result.check_returncode()
        for name in ("linux-settings.png", "linux-bar.png"):
            path = output / name
            if not path.is_file() or not path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
                raise RuntimeError(f"Qt did not save {name}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qml-renderer", choices=("software", "opengl"), default="software")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/screenshots/multiple-bar-items")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    render_linux(output, args.qml_renderer)


if __name__ == "__main__":
    main()
