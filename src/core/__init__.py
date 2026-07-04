import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VERSION_FILE = os.path.join(ROOT, "VERSION")

if os.path.exists(VERSION_FILE):
    with open(VERSION_FILE) as f:
        __version__ = f.read().strip()
else:
    __version__ = "0.0.0"
