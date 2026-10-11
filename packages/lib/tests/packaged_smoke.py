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


info = run("doctor", "--smoke", "--http-smoke")
assert info["desktop"], info
assert info["conpty"], info
assert info["widget_render"] and info["provider_icons"] and info["native_console"], info
assert info["native_https"], info
runtime = Path(exe).parent / "_internal"
assert not (runtime / "PySide6/opengl32sw.dll").exists()
assert not (runtime / "PySide6/Qt6Network.dll").exists()
assert not (runtime / "winpty").exists()
assert not (runtime / "ucrtbase.dll").exists()
assert not list(runtime.rglob("libssl*.dll"))
assert not list(runtime.rglob("libcrypto*.dll"))
assert not list((runtime / "lib/src/providers").rglob("*.sh"))
for family in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
    assert len(list(runtime.rglob(family))) == 1, family
launcher = Path(exe).with_name("ai-status.exe")
assert launcher.stat().st_size < 256 * 1024
desktop = subprocess.run([str(launcher), "doctor", "--smoke"], capture_output=True, text=True,
                         encoding="utf-8", timeout=50, check=True)
assert json.loads(desktop.stdout)["widget_render"], desktop.stdout
# Invalid command arguments must keep the child's nonzero exit status/stderr.
invalid = subprocess.run([str(launcher), "--query"], capture_output=True, text=True,
                         encoding="utf-8", timeout=15)
assert invalid.returncode != 0 and "Usage:" in invalid.stderr, invalid
assert len(info["providers"]) == 29, info
for name in ("claude", "codex", "copilot", "zai", "opencode", "commandcode"):
    diagnostic = run("--query", name)
    assert "_ai_status_error" in diagnostic, (name, diagnostic)
result = run("status")
assert result["providers"] == [], result
assert len(result["errors"]) == 8, result
print("GUI launcher, native HTTPS, desktop dependencies and all registered collectors passed smoke checks.")
