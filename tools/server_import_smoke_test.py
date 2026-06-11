# -*- coding: utf-8 -*-
"""Verify that the standalone server imports without starting it."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["HAWAA_SERVER_PROCESS"] = "1"

from server.config import load_server_config
try:
    from server.flask_server import app
except ModuleNotFoundError as exc:
    if exc.name == "flask":
        app = None
    else:
        raise


def main() -> int:
    cfg = load_server_config()
    assert cfg.port > 0
    if app is None:
        print("⚠️ server_import_smoke_test skipped Flask app import لأن flask غير مثبتة في بيئة الفحص")
        return 0
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    required = {"/api/health", "/api/login", "/api/expenses", "/api/server_info"}
    missing = sorted(required - routes)
    assert not missing, "Missing server routes: " + ", ".join(missing)
    print("✅ server_import_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
