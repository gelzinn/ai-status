"""Read the product version from the root manifest, including frozen builds."""
import json
from pathlib import Path
import re

from .paths import LIB_DIR, PROJECT_ROOT


def read_version(root=None, lib_dir=None, *, required=False):
    """A present manifest is authoritative; VERSION supports older packages only."""
    root = Path(root) if root is not None else PROJECT_ROOT
    lib_dir = Path(lib_dir) if lib_dir is not None else LIB_DIR
    manifest = root / "package.json"
    if manifest.exists() or manifest.is_symlink():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        version = data.get("version") if isinstance(data, dict) else None
    else:
        legacy = lib_dir / "VERSION"
        if not required and not legacy.exists() and not legacy.is_symlink():
            return "0.0.0"
        version = legacy.read_text(encoding="utf-8").strip()
    if not isinstance(version, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version):
        raise ValueError("Product version must be a stable semantic version (x.y.z)")
    return version


__version__ = read_version()
