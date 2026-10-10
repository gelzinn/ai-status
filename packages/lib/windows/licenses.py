"""Collect the installed wheel licenses alongside the dynamically linked bundle."""
from importlib import metadata
from pathlib import Path
import sys

parts = []
for name in ("PySide6-Essentials", "shiboken6", "pyinstaller"):
    distribution = metadata.distribution(name)
    parts.append(f"\n{'=' * 72}\n{name} {distribution.version}\n{'=' * 72}\n")
    found = False
    for item in distribution.files or []:
        if "license" in item.name.lower() or "copying" in item.name.lower():
            path = Path(distribution.locate_file(item))
            if path.is_file():
                try:
                    parts.append(path.read_text(encoding="utf-8"))
                    found = True
                except UnicodeError:
                    pass
    if not found:
        raise SystemExit(f"No license text found in {name}")
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if not python_license.is_file():
    raise SystemExit("Python LICENSE.txt missing from build runtime")
parts.append("\nPython\n" + python_license.read_text(encoding="utf-8"))
parts.append("\nGeist Mono\n" + (Path(__file__).resolve().parents[1] / "assets/fonts/OFL.txt").read_text(encoding="utf-8"))
Path(sys.argv[1]).write_text("\n".join(parts), encoding="utf-8")
