# -*- coding: utf-8 -*-
"""Static smoke checks for phase-3 architecture boundaries."""
from __future__ import annotations

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

MODULES = [
    "database.data_sources.base",
    "database.data_sources.local",
    "database.data_sources.remote",
    "database.data_sources.factory",
    "database.repositories.base_repo",
    "services.network_service",
]


def main() -> int:
    for module_name in MODULES:
        importlib.import_module(module_name)
    print("phase3 architecture smoke test: ok")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush() if "sys" in globals() else None
    sys.stderr.flush() if "sys" in globals() else None
    os._exit(code)
