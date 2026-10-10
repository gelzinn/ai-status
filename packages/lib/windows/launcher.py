"""Build the tiny GUI launcher with the x64 MSVC tools (build-time only)."""
import os
from pathlib import Path
import shutil
import subprocess

source = Path(__file__).resolve().parent
root = source.parents[2]
build = root / "build/windows-launcher"
build.mkdir(parents=True, exist_ok=True)
vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
installation = subprocess.check_output([
    str(vswhere), "-latest", "-products", "*", "-requires",
    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath", "-utf8",
], encoding="utf-8").strip()
if not installation:
    raise SystemExit("Install the x64 MSVC build tools and Windows SDK to build the launcher")
devcmd = Path(installation) / "Common7/Tools/VsDevCmd.bat"
# Capture the compiler environment without printing it (CI may contain secrets).
result = subprocess.run(["cmd.exe", "/d", "/u", "/s", "/c",
                         f'call "{devcmd}" -no_logo -arch=x64 -host_arch=x64 && set'],
                        capture_output=True, check=True)
environment = dict(os.environ)
for line in result.stdout.decode("utf-16le").splitlines():
    key, separator, value = line.partition("=")
    if separator and key:
        environment[key.upper()] = value


def run(name, arguments):
    executable = shutil.which(name, path=environment.get("PATH", environment.get("Path")))
    if not executable:
        raise SystemExit(f"MSVC environment is missing {name}")
    subprocess.run([executable, *arguments], env=environment, cwd=build, check=True)


resource = build / "launcher.rc"
resource.write_text(f'1 ICON "{(root / "build/windows-app.ico").as_posix()}"\n'
                    f'1 24 "{(source / "launcher.manifest").as_posix()}"\n', encoding="utf-8")
run("rc.exe", ["/nologo", "/fo", str(build / "launcher.res"), str(resource)])
run("cl.exe", ["/nologo", "/O1", "/Oi", "/W4", "/WX", "/DUNICODE", "/D_UNICODE",
               str(source / "launcher.c"), str(build / "launcher.res"),
               f'/Fe{root / "dist/ai-status/ai-status.exe"}', "/link", "/NODEFAULTLIB",
               "/ENTRY:wWinMainCRTStartup", "/SUBSYSTEM:WINDOWS", "/MANIFEST:NO",
               "/OPT:REF", "/OPT:ICF", "kernel32.lib", "user32.lib"])
print("Built GUI launcher sharing the CLI runtime.")
