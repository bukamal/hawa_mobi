# -*- coding: utf-8 -*-
from __future__ import annotations
import sys

import os
import tempfile

from reports.account_statement import export_account_statement_html
from reports.share import (
    build_statement_message,
    normalize_phone,
    whatsapp_url,
    file_uri,
    guess_mime,
    ShareResultInfo,
)


def main() -> int:
    records = [
        {
            "id": 1,
            "company_name": "شركة اختبار",
            "amount": 100.0,
            "amount_original": 100.0,
            "currency": "USD",
            "currency_original": "USD",
            "exchange_rate_to_usd": 1.0,
            "type": "incoming",
            "date": "2026-06-11",
            "notes": "قيد اختبار",
            "status": "approved",
        }
    ]
    out = os.path.join(tempfile.gettempdir(), "hawaa_share_test.html")
    path = export_account_statement_html("شركة اختبار", records, output_path=out)
    assert os.path.exists(path), path
    assert guess_mime(path) == "text/html"
    assert file_uri(path).startswith("file:")
    assert normalize_phone("+966 55 123 4567") == "966551234567"
    msg = build_statement_message("شركة اختبار", path)
    assert "شركة اختبار" in msg
    url = whatsapp_url(msg, "+966 55 123 4567")
    assert url.startswith("https://wa.me/966551234567?text=")
    info = ShareResultInfo(True, "test", "ok", path=path)
    assert info.ok and info.method == "test" and info.path == path
    share_source = open(
        os.path.join(os.path.dirname(__file__), "..", "reports", "share.py"),
        encoding="utf-8",
    ).read()
    assert 'getattr(ft, "Share", None)' in share_source
    assert "copy_to_public_downloads" in share_source
    assert "manual_public_downloads" in share_source
    assert "org.kivy.android.PythonActivity" not in share_source
    print("✅ report_share_smoke_test passed")
    return 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush() if "sys" in globals() else None
    sys.stderr.flush() if "sys" in globals() else None
    os._exit(code)
