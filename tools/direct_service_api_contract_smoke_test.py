# -*- coding: utf-8 -*-
"""Static API contract check for direct-service workflow endpoints."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "flask_server.py"
REST = ROOT / "database" / "connection_rest.py"


def main() -> int:
    server = SERVER.read_text(encoding="utf-8")
    rest = REST.read_text(encoding="utf-8")
    for token in [
        '"/api/direct_services"',
        '"/api/direct_services/{reference}"',
        '"/api/direct_services/{reference}/reverse"',
        'supports_direct_services',
        'supports_direct_service_correction',
        'def add_direct_service',
        'def get_direct_services',
        'def get_direct_service',
        'def update_direct_service',
        'def reverse_direct_service',
    ]:
        assert token in server, f"server missing {token}"
    for token in [
        'def add_direct_service',
        'def get_direct_services',
        'def get_direct_service',
        'def update_direct_service',
        'def reverse_direct_service',
        "'/api/direct_services'",
    ]:
        assert token in rest, f"RestClient missing {token}"
    print("direct_service_api_contract_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush(); sys.stderr.flush(); os._exit(code)
