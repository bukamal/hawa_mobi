# -*- coding: utf-8 -*-
"""Ensure reconciliation explanatory note is restored in matching statements."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("HAWAA_DATA_DIR", tempfile.mkdtemp(prefix="hawaa_phase87_recon_note_"))

from reports.account_statement import export_reconciliation_statement_html  # noqa: E402

records = [
    {
        "id": 1,
        "date": "2026-07-14",
        "type": "incoming",
        "amount": 100.0,
        "amount_original": 100.0,
        "currency_original": "USD",
        "notes": "خدمة اختبار",
        "person_name": "عميل اختبار",
        "service_type": "تذكرة سفر",
        "source_ref": "SVC-TEST",
    }
]

html_path = Path(export_reconciliation_statement_html("شركة اختبار", records))
html = html_path.read_text(encoding="utf-8")

required_fragments = [
    "لنا = مبالغ مستحقة لنا على الحساب",
    "له = مبالغ مستحقة للحساب علينا أو مدفوعة منه",
    "هذا الكشف مخصص للمطابقة",
    "لا يُعد مخالصة نهائية",
]
for fragment in required_fragments:
    assert fragment in html, f"Restored reconciliation note fragment is missing: {fragment}"

assert "كشف حساب للمطابقة" in html
assert "خدمة اختبار" in html
assert "يرجى مراجعة الكشف" in html, "Footer review instruction should remain"
print("reconciliation_statement_note_restored_smoke_test passed")
