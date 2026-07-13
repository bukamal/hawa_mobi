# -*- coding: utf-8 -*-
"""Remove sensitive/runtime leftovers before Android APK quality gates.

This script is deliberately conservative: it removes only known runtime/license
artifacts that must never be committed or packaged with the Android client.
It does not touch the real activation implementation at auth/activation.py.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    ROOT / "license.dat",
    ROOT / "network_license.dat",
    ROOT / "auth" / "activation.py.tmp",
]

DIRS = [
    ROOT / ".pytest_cache",
]


def remove_path(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return True


def main() -> int:
    removed: list[str] = []
    for path in FILES + DIRS:
        if remove_path(path):
            removed.append(path.relative_to(ROOT).as_posix())

    if removed:
        print("cleanup_sensitive_source_files removed: " + ", ".join(removed))
    else:
        print("cleanup_sensitive_source_files: no sensitive source files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
