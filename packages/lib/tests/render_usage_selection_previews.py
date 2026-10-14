"""Capture production Usage pages and verify single/multiple bar selection behavior."""

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from unittest.mock import patch

import render_bar_items_previews as bar_previews


LIB = bar_previews.LIB
PROJECT = bar_previews.PROJECT
FILES = ("linux-single-item.png", "linux-multiple-items.png",
         "linux-same-provider-items.png", "linux-unavailable-item.png")


def fixture_snapshots():
    """Build real shared snapshots without credentials, collectors or saved preferences."""
    baseline = bar_previews.fixture_snapshot()
    from core import config, fetch, notifications, quickshell, state

    data = copy.deepcopy(bar_previews.DATA)
    data[0]["metrics"] = [dict(type="weekly", percentage=44, reset_in_seconds=345600)]
    data[0]["reset_credits"] = {"available": 3, "credits": []}
    data[1]["_observed_at"] = time.time()
    data[1]["monetary_credits"] = [dict(id="claude-cloud", title="Cloud credits",
                                       currency="USD", balance=17.50, limit=50,
                                       used=32.50, available=True)]
    cases = [
        [bar_previews.ITEMS[0]],
        copy.deepcopy(bar_previews.ITEMS),
        copy.deepcopy(bar_previews.ITEMS[1:]),
        [bar_previews.ITEMS[0], dict(provider="claude", idx=0, metric="monthly:Unavailable")],
    ]
    snapshots = []
    logos = {name: str(LIB / "assets/providers" / f"{name}.png") for name in ("codex", "claude")}
    with patch.object(config, "available_connections", return_value=["codex", "claude", "kiro"]), \
            patch.object(config, "enabled_connection_order", return_value=["codex", "claude"]), \
            patch.object(config, "connection_info", side_effect=lambda name: {"provider": name, "label": ""}), \
            patch.object(notifications, "load_settings", return_value=baseline["settings"]["notifications"]), \
            patch.object(fetch, "get_version_info", return_value=baseline["version"]):
        for items in cases:
            selected = state.set_selected_items(copy.deepcopy(bar_previews.SELECTED), items)
            snapshots.append(quickshell.build_snapshot(data, selected, logo_paths=logos))
    return snapshots


def render(output, renderer="software"):
    runner = os.environ.get("QMLTESTRUNNER") or shutil.which("qmltestrunner")
    if not runner and Path("/usr/lib/qt6/bin/qmltestrunner").is_file():
        runner = "/usr/lib/qt6/bin/qmltestrunner"
    if not runner:
        raise RuntimeError("Install Qt Quick Test or set QMLTESTRUNNER.")
    output.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (output / name).unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="ai-status-usage-selection-qml-") as directory:
        root = Path(directory)
        for name in ("qs", "Quickshell"):
            shutil.copytree(LIB / "tests/qml" / name, root / name)
        shutil.copytree(LIB / "quickshell", root / "plugin")
        # Record actions instead of launching the installed backend. All page,
        # focus, accessibility and panel rendering comes from production QML.
        shutil.copy2(LIB / "tests/qml/Model.qml", root / "plugin/Model.qml")
        shutil.copytree(LIB / "assets", root / "assets")
        style = root / "qs/Commons/Style.qml"
        style.write_text(style.read_text().replace("cornerRadius: 0", "cornerRadius: 6")
                         .replace('family: "monospace"', 'family: "Geist Mono"'), encoding="utf-8")
        preview = '''
import QtQuick
import QtTest
import qs.Commons
import "plugin" as Plugin

Item {
    id: scene
    width: 1280
    height: 900
    property var snapshots: SNAPSHOTS
    property var files: FILES
    FontLoader { source: "assets/fonts/GeistMono-Regular.ttf" }
    Plugin.Panel { id: panel; width: 380; height: 680 }
    TestCase {
        name: "UsageSelectionPreviews"
        when: windowShown
        function visibleInside(item, scroller) {
            const position = item.mapToItem(scroller, 0, 0)
            verify(position.y >= scroller.navigationInset && position.y + item.height <= scroller.height,
                   item.objectName + " must be fully visible without clipping")
        }
        function test_capture() {
            for (let index = 0; index < scene.snapshots.length; index++) {
                scene.forceActiveFocus()
                Plugin.Model.reset()
                Plugin.Model.snapshot = scene.snapshots[index]
                panel.showUsage()
                panel.open()
                const scroller = findChild(panel, "panel-scroller")
                const surface = findChild(panel, "panel-surface")
                const hint = findChild(panel, "usage-bar-settings")
                scroller.contentY = 0
                wait(1800)
                const multiple = index > 0
                compare(hint.visible, multiple)
                if (multiple) {
                    visibleInside(hint, scroller)
                    compare(hint.text, "Bar items: Settings → Providers")
                    for (const child of hint.children) {
                        if (typeof child.truncated === "boolean" && child.visible && child.text.length > 0)
                            verify(!child.truncated, "The Settings hint must fit on one line")
                    }
                }
                visibleInside(findChild(panel, "usage-provider-codex-0"), scroller)
                visibleInside(findChild(panel, "usage-metric-claude-0-credits:claude-cloud"), scroller)
                const image = grabImage(surface)
                verify(image.width === 380 && image.height > 0 && image.height <= 680)
                image.save(OUTPUT + "/" + scene.files[index])

                const before = JSON.stringify(Plugin.Model.snapshot)
                for (const id of ["usage-provider-codex-0", "usage-provider-claude-0",
                                  "usage-metric-codex-0-weekly", "usage-metric-claude-0-weekly"]) {
                    const row = findChild(panel, id)
                    verify(row !== null)
                    compare(row.activeFocusOnTab, !multiple)
                    compare(row.Accessible.role, multiple ? Accessible.StaticText : Accessible.Button)
                    mouseClick(row)
                    if (multiple) {
                        row.forceActiveFocus()
                        keyClick(Qt.Key_Return)
                        keyClick(Qt.Key_Enter)
                        keyClick(Qt.Key_Space)
                        compare(Plugin.Model.chosen, null)
                    } else {
                        verify(Plugin.Model.chosen !== null, "Single-item clicks must remain usable")
                    }
                }
                compare(JSON.stringify(Plugin.Model.snapshot), before)
                compare(Plugin.Model.saved, null)

                if (multiple) {
                    // These actions open details without altering configured pins.
                    scroller.contentY = 0
                    mouseClick(findChild(panel, "reset-credits-codex-0"))
                    compare(panel.resetProvider.id, "codex")
                    panel.showUsage()
                    wait(100)
                    mouseClick(findChild(panel, "usage-metric-claude-0-credits:claude-cloud"))
                    compare(panel.creditSelection.creditId, "claude-cloud")
                    panel.showUsage()
                    wait(100)
                    compare(JSON.stringify(Plugin.Model.snapshot), before)
                    compare(Plugin.Model.chosen, null)
                    compare(Plugin.Model.saved, null)
                    scroller.contentY = 0
                    mouseClick(hint)
                    verify(panel.configurationPage)
                    compare(findChild(panel, "panel-settings-page").section, "providers")
                    compare(JSON.stringify(Plugin.Model.snapshot), before)
                    panel.showUsage()
                }
            }
            compare(scene.snapshots[2].settings.items.length, 2)
            compare(scene.snapshots[2].settings.items[0].provider, scene.snapshots[2].settings.items[1].provider)
            compare(scene.snapshots[3].settings.items.length, 2)
            compare(scene.snapshots[3].barItems.length, 1)
        }
    }
}
'''
        preview = preview.replace("SNAPSHOTS", json.dumps(fixture_snapshots())).replace("FILES", json.dumps(FILES))
        preview = preview.replace("OUTPUT", json.dumps(str(output)))
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
    for name in FILES:
        if not (output / name).read_bytes().startswith(b"\x89PNG\r\n\x1a\n"):
            raise RuntimeError(f"Qt did not save {name}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qml-renderer", choices=("software", "opengl"), default="software")
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/screenshots/usage-selection")
    args = parser.parse_args()
    render(args.output.resolve(), args.qml_renderer)


if __name__ == "__main__":
    main()
