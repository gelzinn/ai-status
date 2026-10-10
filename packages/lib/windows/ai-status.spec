"""Build one shared runtime. A native GUI launcher is added by build.ps1."""
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
    excludes=["tkinter", "curses", "pytest", "ssl", "_ssl", "_hashlib", "PySide6.QtNetwork", "PySide6.QtQml",
              "PySide6.QtQuick", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtSvg"],
    noarchive=False,
    optimize=2,
)
# This is a raster QWidget app, using qwindows and Windows' native ConPTY.
# Drop optional OpenGL, alternate platform/image/TLS plugins and translations.
# Provider HTTPS uses Windows' WinHTTP/SChannel instead of bundled OpenSSL.
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
                "libcrypto-3-x64.dll", "libssl-3-x64.dll", "libcrypto-3.dll", "libssl-3.dll",
                "ucrtbase.dll"}:
        return False
    if name.startswith("api-ms-win-crt-"):
        return False
    if dest.startswith("lib/assets/") and name.endswith(".svg"):
        return False
    if dest.startswith("lib/src/providers/") and (name.endswith((".sh", ".pyc")) or "/__pycache__/" in dest):
        return False
    return True
analysis.binaries = [entry for entry in analysis.binaries if needed(entry)]
analysis.datas = [entry for entry in analysis.datas if needed(entry)]
archive = PYZ(analysis.pure)
console = EXE(archive, analysis.scripts, [("O", None, "OPTION"), ("O", None, "OPTION")], exclude_binaries=True,
              name="ai-status-cli", console=True, upx=False, icon=icon)
bundle = COLLECT(console, analysis.binaries, analysis.datas,
                 name="ai-status", upx=False)
