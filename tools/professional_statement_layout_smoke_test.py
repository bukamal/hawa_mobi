# -*- coding: utf-8 -*-
"""Validate Phase 76 unified modern statement layout contracts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HAWAA_DATA_DIR", tempfile.mkdtemp(prefix="hawaa_phase76_"))

from reports.account_statement import export_account_statement_html, export_reconciliation_statement_html  # noqa: E402
from reports.config import get_report_settings  # noqa: E402

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

settings = get_report_settings()
cols = {c["key"] for c in settings["account_statement_columns"] if c.get("visible")}
assert {"date", "notes", "reference", "person_name", "service_type", "debit", "credit", "running_balance"} <= cols

recon = Path(export_reconciliation_statement_html("هشام", records))
detail = Path(export_account_statement_html("هشام", records))
recon_cards = Path(export_reconciliation_statement_html("هشام", records, layout_mode="cards"))
recon_html = recon.read_text(encoding="utf-8")
detail_html = detail.read_text(encoding="utf-8")
cards_html = recon_cards.read_text(encoding="utf-8")

assert "كشف حساب للمطابقة" in recon_html
assert "compact-table" in recon_html, "Default reconciliation should use modern compact table"
assert "الزبون: طارق الجباوي" in recon_html, "Passenger must not disappear in compact reconciliation"
assert "الخدمة: تذكرة سفر" in recon_html, "Service must not disappear in compact reconciliation"
assert "Ref:" not in recon_html, "Phase 76 uses Arabic labels instead of legacy Ref in compact metadata"
assert "المرجع" in recon_html and "SVC-20260712-235813-BFFAAB" in recon_html
assert "unicode-bidi:isolate" in recon_html
assert "white-space:nowrap" in recon_html
assert "class='ltr'" in recon_html
assert "class='money" in recon_html
assert "+963" in recon_html or "963" in recon_html, "Header contact should be present and isolated"
assert "لنا = مبالغ مستحقة لنا على الحساب" in recon_html
assert "مخالصة نهائية" in recon_html
assert "48 ساعة" in recon_html

assert "class=\"movement statement-card\"" in cards_html, "Cards layout should remain available from settings"
assert "طارق الجباوي" in cards_html and "SVC-20260712-235813-BFFAAB" in cards_html

assert "كشف حساب تفصيلي" in detail_html
assert "full-table" in detail_html, "Print statement should default to full table"
assert "الزبون / المسافر</th>" in detail_html, "Full print table must preserve passenger column"
assert "الخدمة / البند</th>" in detail_html, "Full print table must preserve service column"
assert "المرجع</th>" in detail_html, "Full print table must preserve reference column"
assert "SVC-20260712-235813-BFFAAB" in detail_html, "Detailed report should preserve full reference by default"

company_view = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
assert "export_reconciliation_statement_html" in company_view
assert "whatsapp_statement_layout_mode" in company_view
assert "مشاركة كشف المطابقة" in company_view

print("professional_statement_layout_smoke_test passed")
