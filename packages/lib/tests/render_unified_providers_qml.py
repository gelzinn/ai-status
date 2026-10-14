"""Capture production Quickshell unified Providers settings with isolated data."""

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from unittest.mock import patch

import render_bar_items_previews as bar_previews


LIB = bar_previews.LIB
PROJECT = bar_previews.PROJECT
FILES = ("linux-providers.png", "linux-providers-reordered.png",
         "linux-providers-bottom.png", "linux-general.png",
         "linux-bar-before.png", "linux-bar-after.png")


def fixture_snapshot(items):
    selected = copy.deepcopy(bar_previews.SELECTED)
    selected.update(items=copy.deepcopy(items), **items[0])
    with patch.object(bar_previews, "SELECTED", selected):
        snapshot = bar_previews.fixture_snapshot()
    # Include one collecting connection with no bar pin and one inactive
    # connection, without touching the developer's real configuration.
    snapshot["settings"]["available"] = ["codex", "claude", "kiro", "cursor"]
    snapshot["settings"]["order"] = ["codex", "claude", "kiro", "cursor"]
    snapshot["settings"]["enabled"] = ["codex", "claude", "kiro"]
    snapshot["settings"]["names"]["cursor"] = "Cursor"
    snapshot["settings"]["providerIds"]["cursor"] = "cursor"
    return snapshot


def render(output, renderer="software"):
    runner = os.environ.get("QMLTESTRUNNER") or shutil.which("qmltestrunner")
    if not runner and Path("/usr/lib/qt6/bin/qmltestrunner").is_file():
        runner = "/usr/lib/qt6/bin/qmltestrunner"
    if not runner:
        raise RuntimeError("Install Qt Quick Test or set QMLTESTRUNNER.")
    output.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (output / name).unlink(missing_ok=True)
    before = fixture_snapshot(bar_previews.ITEMS)
    after = fixture_snapshot([bar_previews.ITEMS[2], *bar_previews.ITEMS[:2]])
    with tempfile.TemporaryDirectory(prefix="ai-status-unified-providers-qml-") as directory:
        root = Path(directory)
        for name in ("qs", "Quickshell"):
            shutil.copytree(LIB / "tests/qml" / name, root / name)
        shutil.copytree(LIB / "quickshell", root / "plugin")
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
    height: 720
    property bool barPreview: false
    property var before: BEFORE_DATA
    property var after: AFTER_DATA
    FontLoader { source: "assets/fonts/GeistMono-Regular.ttf" }
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
        name: "UnifiedProvidersPreviews"
        when: windowShown
        function capture(item, name) {
            const image = grabImage(item)
            verify(image.width > 0 && image.height > 0)
            image.save(OUTPUT + "/" + name)
        }
        function verifyBar(snapshot) {
            compare(snapshot.barItems.length, 3)
            for (let index = 0; index < 3; index++) {
                const label = findChild(widget, "bar-item-label-" + index)
                const logo = findChild(widget, "bar-item-logo-" + index)
                compare(label.text, snapshot.barItems[index].text)
                tryCompare(logo, "status", Image.Ready)
                verify(logo.visible)
            }
        }
        function test_capture() {
            Plugin.Model.reset()
            Plugin.Model.snapshot = scene.before
            const original = JSON.stringify(Plugin.Model.snapshot)
            panel.configure()
            const settings = findChild(panel, "panel-settings-page")
            const scroller = findChild(panel, "panel-scroller")
            const surface = findChild(panel, "panel-surface")
            settings.selectSection("providers")
            compare(settings.section, "providers")
            compare(JSON.stringify(settings.selectedItems), JSON.stringify(scene.before.settings.items))
            verify(settings.enabledProviders.indexOf("kiro") !== -1)
            verify(settings.enabledProviders.indexOf("cursor") === -1)
            verify(!settings.selectedItems.some(item => item.provider === "kiro"))
            verify(!findChild(settings, "bar-item-kiro-0-rolling").checked)
            scroller.contentY = 0
            wait(300)
            compare(surface.height, 680)
            for (const item of settings.selectedItems) {
                const row = findChild(settings, "bar-order-" + item.provider + "-" + item.idx + "-" + item.metric)
                const position = row.mapToItem(scroller, 0, 0)
                verify(position.y >= scroller.navigationInset && position.y + row.height <= scroller.height,
                       "Every selected first/middle/last row must be fully visible")
                const remove = findChild(settings, "bar-order-remove-" + item.provider + "-" + item.idx + "-" + item.metric)
                verify(remove.text.length > 0 || Plugin.PanelIcons.path(remove.iconName).length > 0,
                       "The remove control must render a visible label or bundled icon")
            }
            capture(surface, "linux-providers.png")

            // Move the last identity twice with the production arrow controls.
            for (let index = 0; index < 2; index++) {
                mouseClick(findChild(settings, "bar-order-move-up-claude-0-weekly"))
                wait(100)
            }
            compare(JSON.stringify(settings.selectedItems), JSON.stringify(scene.after.settings.items))
            compare(JSON.stringify(settings.selected), JSON.stringify(scene.after.settings.items[0]))
            compare(JSON.stringify(settings.order), JSON.stringify(scene.before.settings.order))
            scroller.contentY = 0
            wait(200)
            capture(surface, "linux-providers-reordered.png")

            findChild(panel, "panel-key-catcher").forceActiveFocus()
            scroller.contentY = Math.max(0, scroller.contentHeight - scroller.height)
            wait(200)
            for (const name of ["kiro", "cursor"]) {
                const control = findChild(settings, "provider-" + name)
                const position = control.mapToItem(scroller, 0, 0)
                verify(position.y >= scroller.navigationInset && position.y + control.height <= scroller.height)
            }
            capture(surface, "linux-providers-bottom.png")
            settings.selectSection("general")
            scroller.contentY = 0
            wait(200)
            verify(findChild(settings, "refresh-interval-slider").visible)
            verify(!findChild(settings, "provider-codex").visible)
            capture(surface, "linux-general.png")
            compare(JSON.stringify(settings.selectedItems), JSON.stringify(scene.after.settings.items))
            compare(JSON.stringify(Plugin.Model.snapshot), original)
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)

            // Both strip states come from build_snapshot() with the real
            // ordered preference model; neither applies the settings draft.
            scene.barPreview = true
            wait(200)
            verifyBar(scene.before)
            capture(strip, "linux-bar-before.png")
            Plugin.Model.snapshot = scene.after
            wait(200)
            verifyBar(scene.after)
            capture(strip, "linux-bar-after.png")
            compare(Plugin.Model.saved, null)
            compare(Plugin.Model.actions.length, 0)
        }
    }
}
'''
        preview = preview.replace("BEFORE_DATA", json.dumps(before)).replace("AFTER_DATA", json.dumps(after))
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
    parser.add_argument("--output", type=Path, default=PROJECT / "docs/screenshots/unified-provider-settings")
    args = parser.parse_args()
    render(args.output.resolve(), args.qml_renderer)


if __name__ == "__main__":
    main()
