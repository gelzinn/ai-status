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
         "linux-provider-limits.png", "linux-general.png",
         "linux-bar-before.png", "linux-bar-after.png")
PROVIDERS = ["codex", "claude", "kiro", "cursor", "antigravity",
             "commandcode", "zai", "devin", "account:work"]


def fixture_snapshot(provider_order):
    baseline = bar_previews.fixture_snapshot()
    from core import config, fetch, notifications, quickshell, state

    selected = copy.deepcopy(bar_previews.SELECTED)
    state.set_selected_items(selected, state.order_bar_items(bar_previews.ITEMS, provider_order))
    enabled = [name for name in provider_order if name in ("codex", "claude", "kiro")]
    logos = {name: str(LIB / "assets/providers" / f"{name}.png") for name in ("codex", "claude")}
    with patch.object(config, "available_connections", return_value=PROVIDERS), \
            patch.object(config, "enabled_connection_order", return_value=enabled), \
            patch.object(config, "connection_info", side_effect=lambda name: {
                "provider": "codex" if name == "account:work" else name,
                "label": "Engineering workspace" if name == "account:work" else ""}), \
            patch.object(notifications, "load_settings", return_value=baseline["settings"]["notifications"]), \
            patch.object(fetch, "get_version_info", return_value=baseline["version"]):
        return quickshell.build_snapshot(copy.deepcopy(bar_previews.DATA), selected, logo_paths=logos)


def render(output, renderer="software"):
    runner = os.environ.get("QMLTESTRUNNER") or shutil.which("qmltestrunner")
    if not runner and Path("/usr/lib/qt6/bin/qmltestrunner").is_file():
        runner = "/usr/lib/qt6/bin/qmltestrunner"
    if not runner:
        raise RuntimeError("Install Qt Quick Test or set QMLTESTRUNNER.")
    output.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        (output / name).unlink(missing_ok=True)
    (output / "linux-providers-bottom.png").unlink(missing_ok=True)
    before = fixture_snapshot(PROVIDERS)
    after = fixture_snapshot(["claude", "codex", *PROVIDERS[2:]])
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
        # Keep the host's viewport at the normal maximum while testing a short,
        # compact list. The production plugin still controls all row rendering.
        host = root / "qs/Ui/KeyboardPanel.qml"
        host.write_text(host.read_text().replace("return Math.min(value + 32, cap)", "return cap"), encoding="utf-8")
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
            verify(!settings.selectedItems.some(item => item.provider === "cursor"))
            scroller.contentY = 0
            wait(300)
            compare(surface.height, 680)
            for (const index of [0, 4, settings.order.length - 1]) {
                const row = findChild(settings, "provider-row-" + settings.order[index])
                const position = row.mapToItem(scroller, 0, 0)
                verify(position.y >= scroller.navigationInset && position.y + row.height <= scroller.height,
                       "First/middle/last provider rows must be fully visible")
            }
            for (const provider of settings.order) {
                for (const prefix of ["provider-", "provider-bar-"]) {
                    const control = findChild(settings, prefix + provider)
                    const indicator = findChild(control, control.objectName + "-indicator")
                    verify(indicator !== null && indicator.width === 14 && indicator.width <= control.width)
                    const glyph = indicator.children.find(child => child.name === "check")
                    verify(glyph !== undefined)
                    compare(glyph.visible, control.checked)
                    for (const child of control.children) {
                        if (typeof child.truncated === "boolean" && child.visible && child.text.length > 0)
                            verify(!child.truncated, "Active/Bar checkbox content must not be elided")
                    }
                }
            }
            compare(findChild(settings, "bar-order-codex-0-weekly"), null)
            const kiro = findChild(settings, "provider-kiro")
            verify(kiro.Accessible.checked)
            verify(!findChild(settings, "provider-bar-kiro").Accessible.checked)
            verify(!findChild(settings, "provider-cursor").Accessible.checked)
            verify(findChild(settings, "provider-limits-account:work").Accessible.name.indexOf("Engineering workspace") !== -1)
            capture(surface, "linux-providers.png")

            // One provider arrow moves every selected limit in that group.
            mouseClick(findChild(settings, "provider-move-up-claude"))
            wait(100)
            compare(JSON.stringify(settings.selectedItems), JSON.stringify(scene.after.settings.items))
            compare(JSON.stringify(settings.selected), JSON.stringify(scene.after.settings.items[0]))
            compare(JSON.stringify(settings.order), JSON.stringify(scene.after.settings.order))
            scroller.contentY = 0
            wait(200)
            capture(surface, "linux-providers-reordered.png")

            const menu = findChild(settings, "provider-limits-claude")
            mouseClick(menu)
            tryCompare(menu, "popupOpen", true)
            wait(200)
            for (const item of scene.after.settings.items.filter(item => item.provider === "claude")) {
                const option = findChild(menu.popupItem, "bar-item-" + item.provider + "-" + item.idx + "-" + item.metric)
                verify(option !== null && option.Accessible.checked)
            }
            verify(!findChild(menu.popupItem, "bar-item-claude-0-weekly:Fable").Accessible.checked)
            capture(surface, "linux-provider-limits.png")
            menu.dismiss()
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
