import os
from .paths import LIB_DIR

ROOT = str(LIB_DIR)
VERSION_FILE = os.path.join(ROOT, "VERSION")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE) as f:
        __version__ = f.read().strip()
else:
    __version__ = "0.0.0"
