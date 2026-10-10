"""Desktop/CLI entry point; also used by PyInstaller."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.cli import main

if __name__ == "__main__":
    main()
