# -*- coding: utf-8 -*-
"""Smoke test for Phase 91 direct-service edit/reversal integrity."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_direct_correction_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import DirectServiceRepository, ExpenseRepository, AuditRepository
    from reports.reporting_center import PERIOD_ALL, REPORT_DIRECT_SERVICES, ReportingCenterService

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    repo = DirectServiceRepository()
    result = repo.add({
        "company_name": "عميل مباشر",
        "person_name": "مازن مباشر",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 200,
        "cost_amount_original": 150,
        "supplier_company_name": "مورد مباشر",
        "currency_original": "USD",
        "date": "2026-07-15",
        "notes": "قبل التصحيح",
    })
    ref = result["reference"]
    assert abs(float(result["profit_base"]) - 50.0) < 0.001

    before = repo.get_by_reference(ref)
    assert before["status"] == "open"
    assert before.get("supplier_expense_id")

    updated = repo.update(ref, {
        "company_name": "عميل مباشر معدل",
        "person_name": "مازن مباشر",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 260,
        "cost_amount_original": 0,
        "supplier_company_name": "",
        "currency_original": "USD",
        "date": "2026-07-16",
        "notes": "بعد التصحيح",
    }, edit_reason="تصحيح الخدمة إلى تكلفة داخلية صفر")
    assert updated["supplier_expense_id"] in (None, "")
    assert abs(float(updated["profit_base"]) - 260.0) < 0.001

    expenses = ExpenseRepository()
    client_rows = [r for r in expenses.get_by_company("عميل مباشر معدل", convert_to_display=False) if r.get("source_ref") == ref]
    old_client_rows = [r for r in expenses.get_by_company("عميل مباشر", convert_to_display=False) if r.get("source_ref") == ref]
    supplier_rows = [r for r in expenses.get_by_company("مورد مباشر", convert_to_display=False) if r.get("source_ref") == ref]
    assert len(client_rows) == 1 and client_rows[0]["source_type"] == "direct_service_client", client_rows
    assert not old_client_rows, old_client_rows
    assert not supplier_rows, supplier_rows
    assert float(client_rows[0]["amount_original"]) == 260.0
    assert client_rows[0]["is_locked"] == 1

    audit = "\n".join(str(r) for r in AuditRepository().get_all())
    assert "تعديل خدمة مباشرة" in audit and "تصحيح الخدمة" in audit, audit

    rc = ReportingCenterService()
    direct_report = rc.build_report(REPORT_DIRECT_SERVICES, period=PERIOD_ALL)
    joined = "\n".join(str(row) for row in direct_report.rows)
    assert "عميل مباشر معدل" in joined and "260" in joined, joined

    rev = repo.reverse(ref, reason="إلغاء الخدمة بعد التصحيح", date="2026-07-17")
    assert rev["reversal_ref"] == f"REV-{ref}", rev
    after = repo.get_by_reference(ref)
    assert after["status"] == "reversed"
    rev_rows = [r for r in expenses.get_by_company("عميل مباشر معدل", convert_to_display=False, include_reversed=True) if r.get("source_type") == "direct_service_reversal" and r.get("source_ref") == ref]
    assert len(rev_rows) == 1 and rev_rows[0]["type"] == "outgoing", rev_rows

    direct_report_after = rc.build_report(REPORT_DIRECT_SERVICES, period=PERIOD_ALL)
    assert direct_report_after.summary[0]["value"] == "0", direct_report_after.summary

    try:
        repo.update(ref, {
            "company_name": "عميل مباشر معدل",
            "person_name": "مازن مباشر",
            "service_type": "تأشيرة سياحية",
            "sale_amount_original": 300,
            "cost_amount_original": 0,
            "supplier_company_name": "",
            "currency_original": "USD",
            "date": "2026-07-18",
            "notes": "غير مسموح",
        }, edit_reason="محاولة بعد العكس")
        raise AssertionError("reversed direct service was editable")
    except Exception as exc:
        assert "معكوس" in str(exc), str(exc)

    print("direct_service_correction_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
