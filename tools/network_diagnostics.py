# -*- coding: utf-8 -*-
"""Small operator diagnostic for Android/Windows network mode.

Usage:
    python tools/network_diagnostics.py http://192.168.1.100:8000
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from database.connection_rest import RestClient
from services.network_service import NetworkService


def main() -> int:
    raw_url = sys.argv[1] if len(sys.argv) > 1 else ""
    if not raw_url:
        print("Usage: python tools/network_diagnostics.py http://SERVER_IP:8000")
        return 2
    try:
        url = NetworkService.normalize_server_url(raw_url)
    except Exception as exc:
        print(f"❌ عنوان غير صالح: {exc}")
        return 2
    result = NetworkService.check_connection(url)
    print(("✅" if result.ok else "❌"), result.message)
    print("URL:", result.server_url)
    try:
        client = RestClient(url)
        health = client.health()
        caps = client.capabilities()
        print("Health:", health)
        print("Capabilities:")
        print("  api_contract_version:", caps.get("api_contract_version"))
        print("  currency_contract:", caps.get("currency_contract"))
        print("  supports_historic_currency_snapshot:", caps.get("supports_historic_currency_snapshot"))
        print("  supports_amount_base:", caps.get("supports_amount_base"))
        print("  supports_exchange_rate_history:", caps.get("supports_exchange_rate_history"))
    except Exception as exc:
        print("⚠️ تعذر قراءة تفاصيل الخادم:", exc)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
