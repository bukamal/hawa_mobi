# -*- coding: utf-8 -*-
"""Static/runtime checks for Android QR pairing contract."""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    server = read("server/flask_server.py")
    rest = read("database/connection_rest.py")
    service = read("services/pairing_service.py")
    settings = read("views/settings_mobile_view.py")
    login = read("views/login_view.py")

    required_server = [
        'PAIRING_CONTRACT_VERSION = "hawaa-mobile-pairing-v1"',
        '@app.post("/api/mobile/pairing-token")',
        '@app.post("/api/mobile/pair")',
        'PAIRING_TOKEN_TTL_SECONDS = 300',
        'pairing_token',
        'does not log in',
    ]
    missing = [term for term in required_server if term not in server]
    assert not missing, "server mobile pairing contract missing: " + ", ".join(missing)
    assert "@require_roles(\"admin\", \"manager\")" in server, "pairing-token generation must require admin/manager"
    assert "def pair_mobile" in rest and "'/api/mobile/pair'" in rest, "RestClient must validate pairing token"
    assert "'/api/mobile/pair'" in rest and "_requires_auth" in rest, "/api/mobile/pair must be public before login"
    assert "MobilePairingService" in service and "pair_from_qr_text" in service, "Android must expose QR pairing service"
    assert "NetworkService.save_mode(\"client\"" in service, "successful pairing must save client network mode"
    assert "currency_contract" in service and "historic-currency-snapshot-v1" in service, "pairing must validate currency contract"
    assert "_open_qr_pairing_dialog" in settings and "ربط عبر QR" in settings, "Settings must expose QR pairing dialog"
    assert "_open_qr_pairing_dialog" in login and "ربط مع Windows عبر QR" in login, "Login must expose QR pairing before auth"

    from services.pairing_service import MobilePairingService
    expires = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    payload = {
        "app": "hawaa-sham",
        "kind": "mobile_pairing",
        "pairing_contract": "hawaa-mobile-pairing-v1",
        "currency_contract": "historic-currency-snapshot-v1",
        "server_url": "http://192.168.1.50:8000",
        "pairing_token": "abc",
        "expires_at": expires,
    }
    parsed = MobilePairingService.validate_payload(MobilePairingService.parse_qr_text(json.dumps(payload, ensure_ascii=False)))
    assert parsed["server_url"] == "http://192.168.1.50:8000"
    assert parsed["pairing_token"] == "abc"
    local = dict(payload)
    local["server_url"] = "http://127.0.0.1:8000"
    parsed_local = MobilePairingService.validate_payload(local)
    assert parsed_local["server_url"] == "http://127.0.0.1:8000"
    zero = dict(payload)
    zero["server_url"] = "http://0.0.0.0:8000"
    parsed_zero = MobilePairingService.validate_payload(zero)
    assert parsed_zero["server_url"] == "http://127.0.0.1:8000"
    print("✅ mobile_pairing_contract_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    os._exit(code)
