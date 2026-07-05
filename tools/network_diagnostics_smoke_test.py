# -*- coding: utf-8 -*-
from __future__ import annotations


def main() -> int:
    from services.network_diagnostics_service import classify_connection_error, build_diagnostic_steps

    h1 = classify_connection_error("http://192.168.43.132:8000", "Network is unreachable")
    assert "الشبكة" in h1.title
    assert h1.technical
    steps = build_diagnostic_steps("http://192.168.43.132:8000")
    assert any("/api/health" in s for s in steps)
    assert any("192.168.43" in s for s in steps)
    h2 = classify_connection_error("http://127.0.0.1:8000", "connection refused")
    assert h2.title in {"الخادم رفض الاتصال", "عنوان محلي"}
    print("✅ network_diagnostics_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
