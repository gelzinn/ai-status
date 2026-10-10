"""Build and smoke-test the installable library from an exported release tree."""

import argparse
import gzip
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile


def build(source, output, version):
    source, output = Path(source), Path(output)
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("A stable version is required")
    lib = source / "packages/lib"
    if (lib / "VERSION").read_text().strip() != version:
        raise ValueError("Release version and VERSION disagree")
    for required in (lib / "install.sh", lib / "src/bin/ai-status", source / "packages/shared/providers/providers.json"):
        if not required.is_file():
            raise ValueError(f"Release is missing {required.relative_to(source)}")
    # Parse every Python file and import the CLI without running a provider or
    # looking at the runner's credentials. No pycache is written into the package.
    for script in lib.rglob("*.py"):
        compile(script.read_bytes(), str(script), "exec")
    with tempfile.TemporaryDirectory(prefix="ai-status-smoke-") as isolated:
        env = {**os.environ, "HOME": isolated, "PYTHONDONTWRITEBYTECODE": "1"}
        subprocess.run(["python3", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import core.cli", str(lib / "src")],
                       env=env, check=True, timeout=30)
        result = subprocess.run(["python3", str(lib / "src/bin/ai-status"), "--version"],
                                env=env, check=True, capture_output=True, text=True, timeout=30)
        if result.stdout.strip() != version:
            raise ValueError("Packaged CLI does not report the expected version")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f"ai-status-v{version}.tar.gz"
    with archive.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w") as tar:
            for package in ("packages/lib", "packages/shared"):
                for item in sorted((source / package).rglob("*")):
                    if "__pycache__" in item.parts or item.suffix == ".pyc":
                        continue
                    if item.is_symlink():
                        raise ValueError(f"Unexpected symlink: {item}")
                    if item.is_file():
                        info = tar.gettarinfo(str(item), arcname=item.relative_to(source).as_posix())
                        info.uid = info.gid = info.mtime = 0
                        info.uname = info.gname = ""
                        with item.open("rb") as data:
                            tar.addfile(info, data)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {archive.name}\n")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    print(build(args.source, args.output, args.version))
