from __future__ import annotations

import os
import sys
from pathlib import Path


def prepare_qt_runtime() -> None:
    """Make PySide6 and shiboken DLL directories visible in frozen builds."""
    if not getattr(sys, "frozen", False) or os.name != "nt":
        return

    base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    directories = [base / "PySide6", base / "shiboken6", base]
    valid = [str(path) for path in directories if path.exists()]

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join([*valid, old_path])
    for directory in valid:
        try:
            os.add_dll_directory(directory)
        except OSError:
            pass


prepare_qt_runtime()

from novel_scraper.gui import main


if __name__ == "__main__":
    raise SystemExit(main())
