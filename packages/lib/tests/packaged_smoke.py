"""Run on a clean Windows profile against the built/installed CLI."""
import json
from pathlib import Path
import subprocess
import sys

def run_process(command, *, phase, timeout=50, check=True):
    """Keep subprocess errors fatal while exposing the captured failure details."""
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              encoding="utf-8", timeout=timeout, check=check)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        reason = (f"exit status {error.returncode}" if isinstance(error, subprocess.CalledProcessError)
                  else f"timeout after {error.timeout}s")
        print(f"Packaged smoke failed during {phase}: {reason}", file=sys.stderr)
        print("Command: " + subprocess.list2cmdline(command), file=sys.stderr)
        for name, output in (("stdout", error.stdout), ("stderr", error.stderr)):
            # TimeoutExpired can retain bytes even when text=True was supplied.
            if isinstance(output, bytes):
                output = output.decode("utf-8", errors="replace")
            if output:
                print(f"Captured {name}:\n{output.rstrip()}", file=sys.stderr)
        raise


def run(exe, *args, phase):
    result = run_process([exe, *args], phase=phase)
    return json.loads(result.stdout)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    exe = str(Path(argv[0]).resolve())
    info = run(exe, "doctor", "--smoke", "--http-smoke", phase="runtime and native HTTPS")
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
    desktop = run_process([str(launcher), "doctor", "--smoke"], phase="GUI launcher")
    assert json.loads(desktop.stdout)["widget_render"], desktop.stdout
    # Invalid command arguments must keep the child's nonzero exit status/stderr.
    invalid = run_process([str(launcher), "--query"], phase="invalid CLI arguments", timeout=15, check=False)
    assert invalid.returncode != 0 and "Usage:" in invalid.stderr, invalid
    assert len(info["providers"]) == 29, info
    for name in ("claude", "codex", "copilot", "zai", "opencode", "commandcode"):
        diagnostic = run(exe, "--query", name, phase=f"credential-free {name} collector")
        assert "_ai_status_error" in diagnostic, (name, diagnostic)
    result = run(exe, "status", phase="status with a clean profile")
    assert result["providers"] == [], result
    assert len(result["errors"]) == 8, result
    print("GUI launcher, native HTTPS, desktop dependencies and all registered collectors passed smoke checks.")


if __name__ == "__main__":
    main()
