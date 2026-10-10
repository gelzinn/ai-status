"""Build both the windowed app and console collector into one portable folder."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

lib = Path(SPECPATH).parent
icon = str(lib.parents[1] / "build/windows-app.ico")
analysis = Analysis(
    [str(lib / "src/windows.py")],
    pathex=[str(lib / "src")],
    binaries=[],
    datas=[(str(lib / "src/providers"), "lib/src/providers"),
           (str(lib / "VERSION"), "lib"),
           (str(lib / "assets"), "lib/assets"),
           (str(lib.parent / "shared/providers/providers.json"), "lib/assets"),
           (str(lib.parents[1] / "LICENSE"), "."),
           (str(lib / "windows/THIRD_PARTY.md"), ".")]
          + collect_data_files("PySide6", includes=["**/licenses/**", "**/LICENSE*"]),
    hiddenimports=["core.provider_http", "core.console", "html", "datetime"],
    excludes=["tkinter", "curses", "pytest", "PySide6.QtNetwork", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg"],
    noarchive=False,
)
# This is a raster QWidget app, using qwindows and Windows' native ConPTY.
# Drop optional OpenGL, alternate platform/image/TLS plugins and translations.
# Python's own SSL libraries remain for provider APIs.
platforms = {"qwindows.dll", "qoffscreen.dll"}
def needed(entry):
    dest = entry[0].replace("\\", "/")
    name = Path(dest).name.lower()
    if dest.startswith("PySide6/translations/"):
        return False
    if dest.startswith("PySide6/plugins/"):
        if "/platforms/" in dest:
            return name in platforms
        return False
    if name in {"opengl32sw.dll", "qt6network.dll", "qt6svg.dll",
                "libcrypto-3-x64.dll", "libssl-3-x64.dll"}:
        return False
    if dest.startswith("lib/assets/") and name.endswith(".svg"):
        return False
    return True
analysis.binaries = [entry for entry in analysis.binaries if needed(entry)]
analysis.datas = [entry for entry in analysis.datas if needed(entry)]
archive = PYZ(analysis.pure)
desktop = EXE(archive, analysis.scripts, [], exclude_binaries=True,
              name="ai-status", console=False, upx=False, icon=icon)
console = EXE(archive, analysis.scripts, [], exclude_binaries=True,
              name="ai-status-cli", console=True, upx=False, icon=icon)
bundle = COLLECT(desktop, console, analysis.binaries, analysis.datas,
                 name="ai-status", upx=False)
