# -*- coding: utf-8 -*-
"""Static contract check for service-case editing endpoints."""
from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
server = (ROOT / "server" / "flask_server.py").read_text(encoding="utf-8")
rest = (ROOT / "database" / "connection_rest.py").read_text(encoding="utf-8")
required_server = [
    '"/api/service_cases/{reference}"',
    'supports_service_case_editing',
    '@app.get("/api/service_cases/<path:reference>")',
    '@app.put("/api/service_cases/<path:reference>")',
    'def update_service_case',
]
for needle in required_server:
    assert needle in server, needle
required_rest = [
    'def get_service_case',
    'def update_service_case',
    "'/api/service_cases/{quote",
]
for needle in required_rest:
    assert needle in rest, needle
print("service_case_edit_api_contract_smoke_test passed")
