"""Render the production Linux update panel with sample data and no updater.

Requires PySide6. Uses Qt Quick's offscreen software renderer by default.
The daemon and Omarchy host are the same fixtures used by run_qml_tests.py.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest import mock


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[3] / "docs/screenshots/update-progress")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source / "src"))
    from core import updates
    with mock.patch.object(updates, "_installation", return_value=("omarchy", {})), \
         mock.patch.object(updates.fetch, "get_version_info", return_value={"current": "0.15.0", "latest": "0.16.0"}), \
         mock.patch.object(updates.shutil, "which", return_value="/usr/bin/omarchy"):
        guide = updates.update_guide()

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    os.environ["QML_XHR_ALLOW_FILE_READ"] = "1"
    from PySide6.QtCore import QMetaObject, QTimer, Qt, QUrl
    from PySide6.QtGui import QColor, QGuiApplication, QSurfaceFormat
    from PySide6.QtQuick import QQuickItem, QQuickView, QQuickWindow

    QQuickWindow.setDefaultAlphaBuffer(True)
    app = QGuiApplication([])
    view = QQuickView()
    surface_format = QSurfaceFormat()
    surface_format.setAlphaBufferSize(8)
    view.setFormat(surface_format)
    view.setColor(QColor("transparent"))
    view.setFlags(Qt.FramelessWindowHint)
    with tempfile.TemporaryDirectory(prefix="ai-status-update-progress-qml-") as directory:
        root = Path(directory)
        shutil.copytree(source / "tests/qml/qs", root / "qs")
        shutil.copytree(source / "tests/qml/Quickshell", root / "Quickshell")
        shutil.copytree(source / "quickshell", root / "plugin")
        shutil.copy2(source / "tests/qml/Model.qml", root / "plugin/Model.qml")
        shutil.copytree(source / "assets", root / "assets")
        style = root / "qs/Commons/Style.qml"
        style.write_text(style.read_text().replace("cornerRadius: 0", "cornerRadius: 6"))
        color = root / "qs/Commons/Color.qml"
        color.write_text(color.read_text().replace('accent: "#aaaaaa"', 'accent: "#89b4fa"'))
        preview = root / "Preview.qml"
        preview.write_text("""import QtQuick
import "plugin" as Plugin
Item {
    width: 380; height: 800
    Plugin.Panel { id: panel; width: 380; height: 780 }
    function initialize() {
        Plugin.Model.reset()
        const snapshot = JSON.parse(JSON.stringify(Plugin.Model.snapshot))
        snapshot.version = {current: "0.15.0", latest: "0.16.0", has_update: true}
        snapshot.update = """ + json.dumps(guide) + """
        Plugin.Model.snapshot = snapshot
        panel.open()
        panel.showUpdate()
    }
    function command() { findUpdatePage().commandExpanded = true }
    function findUpdatePage() {
        function find(item) {
            if (item.objectName === "panel-update-page") return item
            for (const child of item.children) {
                const result = find(child)
                if (result) return result
            }
            return null
        }
        return find(panel)
    }
    function checking() {
        findUpdatePage().commandExpanded = false
        Plugin.Model.startUpdate()
        Plugin.Model.updateMessage = "Checking the latest stable release…"
    }
    function opening() {
        Plugin.Model.updateStage = "opening"
        Plugin.Model.updateMessage = "Opening the updater in a terminal…"
    }
    function terminal() {
        Plugin.Model.updateStage = "complete"
        Plugin.Model.updateMessage = "The updater is open in a terminal. Follow its progress there."
        Plugin.Model.updateRunning = false
    }
    function error() {
        Plugin.Model.updateStage = "error"
        Plugin.Model.updateMessage = ""
        Plugin.Model.updateRunning = false
        Plugin.Model.updateError = "No supported terminal found. Run the terminal command, or try again."
    }
    function retry() {
        Plugin.Model.startUpdate()
        Plugin.Model.updateMessage = "Checking the latest stable release…"
    }
    function current() {
        Plugin.Model.updateStage = "complete"
        findUpdatePage().commandExpanded = false
        Plugin.Model.updateMessage = "AI Status is already up to date."
        Plugin.Model.updateRunning = false
    }
}
""")
        view.engine().addImportPath(str(root))
        view.setSource(QUrl.fromLocalFile(str(preview)))
        if view.status() == QQuickView.Error:
            raise RuntimeError([error.toString() for error in view.errors()])
        view.show()
        item = view.rootObject()
        QMetaObject.invokeMethod(item, "initialize", Qt.DirectConnection)
        surface = item.findChild(QQuickItem, "panel-surface")
        stages = [(None, "linux-guide.png"), ("command", "linux-command.png"),
                  ("checking", "linux-checking.png"), ("opening", "linux-opening.png"),
                  ("terminal", "linux-terminal.png"), ("error", "linux-error.png"),
                  ("retry", "linux-retry.png"), ("current", "linux-up-to-date.png")]
        retained = []

        def next_stage():
            if not stages:
                app.quit()
                return
            method, filename = stages.pop(0)
            if method:
                QMetaObject.invokeMethod(item, method, Qt.DirectConnection)
            QTimer.singleShot(350, lambda: capture(filename))

        def capture(filename):
            item.findChild(QQuickItem, "panel-key-catcher").forceActiveFocus(Qt.OtherFocusReason)
            grab = surface.grabToImage()
            retained.append(grab)

            def ready():
                if not grab.saveToFile(str(args.output / filename)):
                    app.exit(1)
                    return
                print(filename, grab.image().width(), grab.image().height(), flush=True)
                QTimer.singleShot(0, next_stage)

            grab.ready.connect(ready)

        QTimer.singleShot(800, next_stage)
        QTimer.singleShot(15000, lambda: app.exit(2))
        return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
