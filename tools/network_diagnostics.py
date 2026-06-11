# -*- coding: utf-8 -*-
"""Small operator diagnostic for network mode.

Usage:
    python tools/network_diagnostics.py http://192.168.1.100:8000
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
