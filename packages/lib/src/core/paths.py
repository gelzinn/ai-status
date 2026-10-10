"""Platform paths shared by the CLI, collectors and packaged desktop app."""
import json
import os
from pathlib import Path
import sys
import tempfile

IS_WINDOWS = sys.platform == "win32"
LIB_DIR = (Path(sys._MEIPASS) / "lib" if getattr(sys, "frozen", False)
           else Path(__file__).resolve().parents[2])
PROVIDERS_DIR = LIB_DIR / "src" / "providers"
CONFIG_DIR = (Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "ai-status"
              if IS_WINDOWS else Path.home() / ".config/ai-status")
CACHE_DIR = (Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "ai-status/cache"
             if IS_WINDOWS else Path.home() / ".cache/ai-status")
RUNTIME_DIR = CACHE_DIR / "runtime" if IS_WINDOWS else Path(tempfile.gettempdir())
LOG_FILE = CACHE_DIR / "ai-status-error.log" if IS_WINDOWS else Path("/tmp/ai-status-error.log")


def atomic_json(path, data):
    """Use a distinct temporary file for every writer; close before Windows replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as stream:
            return json.load(stream)
    except (OSError, ValueError):
        return {}


def opencode_file(name):
    # OpenCode uses XDG data paths on Windows too. Honor explicit overrides.
    root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return root / "opencode" / name
