"""Exercise production QML pages with a fake daemon and Omarchy theme."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    tests = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="ai-status-qml-") as directory:
        root = Path(directory)
        shutil.copytree(tests / "qml", root, dirs_exist_ok=True)
        plugin = root / "plugin"
        plugin.mkdir()
        for name in ("Panel.qml", "UsagePage.qml", "UsageBar.qml", "StableList.js", "ResetCreditsPage.qml", "SettingsPage.qml", "PanelButton.qml", "PanelSelect.qml", "PanelIcon.qml", "AboutPage.qml", "qmldir"):
            shutil.copy2(tests.parent / "quickshell" / name, plugin / name)
        shutil.copy2(root / "Model.qml", plugin / "Model.qml")
        shutil.copytree(tests.parent / "assets/providers", root / "assets/providers")
        shutil.copy2(tests.parent / "assets/app.png", root / "assets/app.png")
        env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software")
        return subprocess.call([
            env.get("QMLTESTRUNNER", "/usr/lib/qt6/bin/qmltestrunner"),
            "-input", str(root), "-import", str(root),
        ], env=env)


if __name__ == "__main__":
    raise SystemExit(main())
