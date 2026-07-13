# -*- coding: utf-8 -*-
"""Static checks for the public Android/Windows pairing capabilities contract."""
from __future__ import annotations
import os

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server" / "flask_server.py"
REST = ROOT / "database" / "connection_rest.py"
NETWORK = ROOT / "services" / "network_service.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    server = read(SERVER)
    rest = read(REST)
    network = read(NETWORK)

    assert '@app.get("/api/capabilities")' in server, "server must expose public /api/capabilities"
    assert 'API_CONTRACT_VERSION = "2026.07.mobile-v1"' in server, "missing API contract version"
    assert 'CURRENCY_CONTRACT_VERSION = "historic-currency-snapshot-v1"' in server, "missing currency contract version"
    assert 'supports_historic_currency_snapshot' in server, "capabilities must declare historic currency support"
    assert 'supports_amount_base' in server, "capabilities must declare amount_base support"
    assert 'supports_exchange_rate_history' in server, "capabilities must declare exchange-rate history support"
    assert 'supports_payment_reminders' in server, "capabilities must declare payment reminder support"
    assert 'supports_audit_post' in server, "capabilities must declare audit POST support"
    assert 'supports_expense_summary' in server, "capabilities must declare expense summary support"

    route_names = set(re.findall(r'"(/api/[^"]+)"', server))
    required = {
        "/api/health",
        "/api/capabilities",
        "/api/login",
        "/api/expenses",
        "/api/expenses/summary",
        "/api/payment_reminders",
        "/api/payment_reminders/count_waiting",
        "/api/exchange_rate_history",
        "/api/mobile/pairing-token",
        "/api/mobile/pair",
    }
    missing = sorted(required - route_names)
    assert not missing, "required pairing routes are not declared: " + ", ".join(missing)

    assert "def capabilities" in rest, "RestClient must support capabilities()"
    assert "'/api/capabilities'" in rest or '"/api/capabilities"' in rest, "RestClient must call /api/capabilities"
    assert "historic-currency-snapshot-v1" in network, "NetworkService must validate the currency contract"
    assert "hawaa-mobile-pairing-v1" in server, "server must expose a stable mobile pairing contract"
    print("✅ api_capabilities_contract_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush() if "sys" in globals() else None
    sys.stderr.flush() if "sys" in globals() else None
    os._exit(code)
