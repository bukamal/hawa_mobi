# -*- coding: utf-8 -*-
"""Validate Phase 71 mobile/WhatsApp statement layout contracts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HAWAA_DATA_DIR", tempfile.mkdtemp(prefix="hawaa_phase71_"))

from reports.account_statement import export_account_statement_html, export_reconciliation_statement_html  # noqa: E402

records = [
    {
        "id": 106,
        "date": "2026-05-07",
        "type": "incoming",
        "amount": 355.0,
        "amount_original": 355.0,
        "currency_original": "USD",
        "notes": "دمشق الدوحة",
        "person_name": "عبد المجيد السويداني",
        "service_type": "تذكرة سفر",
        "source_ref": "106",
    },
    {
        "id": 108,
        "date": "2026-05-18",
        "type": "outgoing",
        "amount": 710.0,
        "amount_original": 710.0,
        "currency_original": "USD",
        "notes": "تسديد",
        "service_type": "تسديد",
        "source_ref": "108",
    },
    {
        "id": 200,
        "date": "2026-07-12",
        "type": "incoming",
        "amount": 165.0,
        "amount_original": 165.0,
        "currency_original": "USD",
        "print_description": "تذكرة سفر - طارق الجباوي",
        "notes": "ملاحظة داخلية لا يجب أن تسبق بيان الطباعة",
        "person_name": "طارق الجباوي",
        "service_type": "تذكرة سفر",
        "source_ref": "SVC-20260712-235813-BFFAAB",
    },
]

recon = Path(export_reconciliation_statement_html("هشام", records))
detail = Path(export_account_statement_html("هشام", records))
recon_html = recon.read_text(encoding="utf-8")
detail_html = detail.read_text(encoding="utf-8")

assert "كشف حساب للمطابقة" in recon_html
assert "class=\"movement\"" in recon_html, "Reconciliation must be card-based, not a wide 8-column table"
assert "الزبون / المسافر</th>" not in recon_html, "External reconciliation must not use separate passenger column"
assert "الخدمة / البنود</th>" not in recon_html, "External reconciliation must fold service into statement body"
assert "SVC-BFFAAB" in recon_html, "Long service refs should be shortened for mobile/WhatsApp"
assert "unicode-bidi:isolate" in recon_html
assert "white-space:nowrap" in recon_html
assert "class='ltr'" in recon_html
assert "class='money" in recon_html
assert "+963" in recon_html or "963" in recon_html, "Header contact should be present and isolated"
assert "مخالصة نهائية" in recon_html and "48 ساعة" in recon_html

assert "كشف حساب تفصيلي" in detail_html
assert "detailed-table" in detail_html
assert "الزبون: طارق الجباوي" in detail_html
assert "Ref: SVC-20260712-235813-BFFAAB" in detail_html, "Detailed report should preserve full reference"
assert "الزبون / المسافر</th>" not in detail_html, "Detailed mobile table should be limited to core columns"

company_view = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
assert "export_reconciliation_statement_html" in company_view
assert "مشاركة كشف المطابقة" in company_view

print("professional_statement_layout_smoke_test passed")
