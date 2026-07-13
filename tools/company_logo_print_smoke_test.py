# -*- coding: utf-8 -*-
"""Verify Android company logo import and print embedding contract."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hawaa_logo_") as tmp:
        os.environ["HAWAA_DATA_DIR"] = tmp
        # 1x1 transparent PNG.
        logo = Path(tmp) / "logo.png"
        logo.write_bytes(
            bytes.fromhex(
                "89504E470D0A1A0A0000000D4948445200000001000000010806000000"
                "1F15C4890000000A49444154789C6360000002000100FFFF03000006000557BFAB"
                "0000000049454E44AE426082"
            )
        )

        from services.company_logo_service import import_logo, image_to_data_uri

        stored = import_logo(str(logo))
        assert Path(stored).exists(), "imported logo must exist in app storage"
        assert "branding" in stored, (
            "logo must be copied into app-owned branding storage"
        )
        assert image_to_data_uri(stored).startswith("data:image/png;base64,"), (
            "logo must be embeddable as data URI"
        )

        import config

        config._CONFIG_FILE = None
        from config import save_company_info

        save_company_info(
            {
                "name": "هوى الشام",
                "address": "اختبار",
                "phone": "000",
                "email": "info@example.com",
                "tax_number": "",
                "logo_path": stored,
            }
        )

        from reports.account_statement import export_account_statement_html

        report = export_account_statement_html(
            "شركة الاختبار",
            [
                {
                    "id": 1,
                    "date": "2026-07-04",
                    "notes": "قيد اختبار",
                    "type": "incoming",
                    "amount": 1.0,
                    "amount_original": 14000.0,
                    "currency_original": "SYP",
                    "exchange_rate_to_usd": 14000.0,
                    "status": "approved",
                }
            ],
        )
        html = Path(report).read_text(encoding="utf-8")
        assert "data:image/png;base64," in html, "print HTML must embed logo as base64"
        assert "file://" not in html, (
            "print HTML must not reference private file:// logo paths"
        )
        assert "class='company-logo'" in html or 'class="company-logo"' in html, (
            "logo CSS class missing"
        )
    print("✅ company_logo_print_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
