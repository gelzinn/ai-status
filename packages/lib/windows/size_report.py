"""Track runtime/download size and fail CI if unnecessary bulk returns."""
from pathlib import Path
import os

root = Path("dist")
version = Path("packages/lib/VERSION").read_text().strip()
sizes = [
    ("Installed folder", sum(path.stat().st_size for path in (root / "ai-status").rglob("*") if path.is_file()), 54),
    ("Portable ZIP", (root / f"ai-status-{version}-windows-x64.zip").stat().st_size, 22),
    ("Installer EXE", (root / f"ai-status-{version}-windows-x64-setup.exe").stat().st_size, 17),
]
report = "| Windows package | Size | Budget |\n| --- | ---: | ---: |\n"
for name, count, budget in sizes:
    report += f"| {name} | {count / 1048576:.2f} MiB | {budget} MiB |\n"
report += "\n| Largest runtime files | Size |\n| --- | ---: |\n"
files = sorted((path for path in (root / "ai-status").rglob("*") if path.is_file()),
               key=lambda path: path.stat().st_size, reverse=True)
for path in files[:10]:
    report += f"| `{path.relative_to(root / 'ai-status').as_posix()}` | {path.stat().st_size / 1048576:.2f} MiB |\n"
print(report)
if os.environ.get("GITHUB_STEP_SUMMARY"):
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
        stream.write(report)
for name, count, budget in sizes:
    if count > budget * 1048576:
        raise SystemExit(f"{name} exceeds its size budget")
