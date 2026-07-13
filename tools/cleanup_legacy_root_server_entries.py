# -*- coding: utf-8 -*-
"""Remove stale root-level server entry files before APK quality gates/builds.

Older snapshots kept network server entrypoints in the project root. The Android
client must keep the real server implementation under server/ only. This script
is intentionally safe: it only removes the two known legacy root files and never
touches server/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY_ROOT_FILES = ["flask_server.py", "run_server.py"]


def main() -> int:
    removed: list[str] = []
    for name in LEGACY_ROOT_FILES:
        path = ROOT / name
        if path.exists() and path.is_file():
            path.unlink()
            removed.append(name)
    if removed:
        print("cleanup_legacy_root_server_entries removed: " + ", ".join(removed))
    else:
        print("cleanup_legacy_root_server_entries: no stale root server files")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
