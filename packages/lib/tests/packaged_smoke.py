"""Run on a clean Windows profile against the built/installed CLI."""
import json
from pathlib import Path
import subprocess
import sys

exe = str(Path(sys.argv[1]).resolve())


def run(*args):
    result = subprocess.run([exe, *args], capture_output=True, text=True,
                            encoding="utf-8", timeout=50, check=True)
    return json.loads(result.stdout)


info = run("doctor", "--smoke")
assert info["desktop"], info
assert info["conpty"], info
assert info["widget_render"] and info["provider_icons"] and info["native_console"], info
runtime = Path(exe).parent / "_internal"
assert not (runtime / "PySide6/opengl32sw.dll").exists()
assert not (runtime / "PySide6/Qt6Network.dll").exists()
assert not (runtime / "winpty").exists()
assert len(info["providers"]) == 8, info
for name in ("claude", "codex", "copilot", "zai", "opencode", "commandcode"):
    diagnostic = run("--query", name)
    assert "_ai_status_error" in diagnostic, (name, diagnostic)
result = run("status")
assert result["providers"] == [], result
assert len(result["errors"]) == 8, result
print("Packaged desktop dependencies and all eight collectors passed smoke checks.")
