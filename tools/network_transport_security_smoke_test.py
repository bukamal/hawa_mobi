# -*- coding: utf-8 -*-
"""Transport rules: HTTPS by default; HTTP only private + explicit opt-in."""

from __future__ import annotations

import os
import tempfile


def must_fail(call, contains: str) -> None:
    try:
        call()
    except ValueError as exc:
        assert contains in str(exc), str(exc)
    else:
        raise AssertionError("expected ValueError")


def main() -> int:
    os.environ["HAWAA_DATA_DIR"] = tempfile.mkdtemp(prefix="hawaa_network_security_")
    from database.migrations import init_database
    from services.network_service import NetworkService

    init_database()
    assert (
        NetworkService.normalize_server_url("example.com:443")
        == "https://example.com:443"
    )
    assert (
        NetworkService.normalize_server_url("https://example.com/api/")
        == "https://example.com"
    )
    must_fail(
        lambda: NetworkService.normalize_server_url(
            "http://192.168.1.20:8000", allow_insecure_http=False
        ),
        "غير مشفر",
    )
    assert (
        NetworkService.normalize_server_url(
            "http://192.168.1.20:8000/api", allow_insecure_http=True
        )
        == "http://192.168.1.20:8000"
    )
    must_fail(
        lambda: NetworkService.normalize_server_url(
            "http://example.com:8000", allow_insecure_http=True
        ),
        "شبكة محلية خاصة",
    )
    must_fail(
        lambda: NetworkService.normalize_server_url("https://user:pass@example.com"),
        "اسم مستخدم",
    )
    print("✅ network_transport_security_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
