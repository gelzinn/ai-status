"""Build both the windowed app and console collector into one portable folder."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

lib = Path(SPECPATH).parent
winpty_data, winpty_binaries, winpty_imports = collect_all("winpty")
analysis = Analysis(
    [str(lib / "src/windows.py")],
    pathex=[str(lib / "src")],
    binaries=winpty_binaries,
    datas=[(str(lib / "src/providers"), "lib/src/providers"),
           (str(lib / "VERSION"), "lib"),
           (str(lib.parents[1] / "LICENSE"), "."),
           (str(lib / "windows/THIRD_PARTY.md"), ".")]
          + winpty_data + collect_data_files("PySide6", includes=["**/licenses/**", "**/LICENSE*"]),
    hiddenimports=["core.provider_http", "core.console", "html", "datetime"] + winpty_imports,
    excludes=["tkinter", "curses", "pytest"],
    noarchive=False,
)
archive = PYZ(analysis.pure)
desktop = EXE(archive, analysis.scripts, [], exclude_binaries=True,
              name="ai-status", console=False, upx=False)
console = EXE(archive, analysis.scripts, [], exclude_binaries=True,
              name="ai-status-cli", console=True, upx=False)
bundle = COLLECT(desktop, console, analysis.binaries, analysis.datas,
                 name="ai-status", upx=False)
