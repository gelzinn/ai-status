"""Compress the portable folder once, at maximum DEFLATE compression."""
from pathlib import Path
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1], "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for path in sorted(Path("dist/ai-status").rglob("*")):
        if path.is_file():
            archive.write(path, path.relative_to("dist"))
