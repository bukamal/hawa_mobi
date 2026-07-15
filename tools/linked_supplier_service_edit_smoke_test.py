# -*- coding: utf-8 -*-
"""Smoke test for Phase 92 linked supplier-service editing.

A service-case correction must update the original service operation, not one
ledger row.  The client ledger row and all supplier rows must stay synchronized
with service_case_components and profitability reports.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_service_case_edit_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import ServiceCaseRepository, ExpenseRepository, AuditRepository
    from reports.reporting_center import PERIOD_ALL, REPORT_PROFIT, REPORT_SERVICES, ReportingCenterService

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    service_repo = ServiceCaseRepository()
    result = service_repo.add({
        "client_company_name": "عميل خدمة قديم",
        "supplier_company_name": "مورد تأشيرات قديم",
        "person_name": "سليم المسافر",
        "service_type": "تأشيرة سياحية",
        "currency_original": "USD",
        "date": "2026-07-10",
        "notes": "قبل التعديل",
        "components": [
            {"service_type": "تأشيرة سياحية", "supplier_company_name": "مورد تأشيرات قديم", "sale_amount_original": 200, "cost_amount_original": 150},
            {"service_type": "سفارة / رسوم سفارة", "supplier_company_name": "رسوم قديمة", "sale_amount_original": 40, "cost_amount_original": 35},
        ],
    })
    ref = result["reference"]
    assert abs(float(result["profit_base"]) - 55.0) < 0.001, result

    updated = service_repo.update(ref, {
        "client_company_name": "عميل خدمة معدل",
        "supplier_company_name": "مورد تأشيرات جديد",
        "person_name": "سليم المسافر معدل",
        "service_type": "تأشيرة سياحية",
        "currency_original": "USD",
        "date": "2026-07-12",
        "notes": "بعد التعديل",
        "components": [
            {"service_type": "تأشيرة سياحية", "supplier_company_name": "مورد تأشيرات جديد", "sale_amount_original": 260, "cost_amount_original": 170},
            {"service_type": "نقل بري", "supplier_company_name": "مورد نقل جديد", "sale_amount_original": 70, "cost_amount_original": 50},
        ],
    }, edit_reason="تصحيح مورد ورسوم الخدمة")
    assert updated["reference"] == ref
    assert len(updated["supplier_expense_ids"]) == 2, updated
    assert abs(float(updated["profit_base"]) - 110.0) < 0.001, updated

    case = service_repo.get_by_reference(ref)
    assert case["client_company_name"] == "عميل خدمة معدل", case
    assert case["person_name"] == "سليم المسافر معدل", case
    assert float(case["sale_amount_original"]) == 330.0, case
    assert float(case["cost_amount_original"]) == 220.0, case
    assert len(case["components"]) == 2, case["components"]
    assert {c["supplier_company_name"] for c in case["components"]} == {"مورد تأشيرات جديد", "مورد نقل جديد"}

    expenses = ExpenseRepository()
    new_client = [r for r in expenses.get_by_company("عميل خدمة معدل", convert_to_display=False) if r.get("source_ref") == ref]
    old_client = [r for r in expenses.get_by_company("عميل خدمة قديم", convert_to_display=False) if r.get("source_ref") == ref]
    old_supplier = [r for r in expenses.get_by_company("مورد تأشيرات قديم", convert_to_display=False) if r.get("source_ref") == ref]
    new_supplier_a = [r for r in expenses.get_by_company("مورد تأشيرات جديد", convert_to_display=False) if r.get("source_ref") == ref]
    new_supplier_b = [r for r in expenses.get_by_company("مورد نقل جديد", convert_to_display=False) if r.get("source_ref") == ref]
    assert len(new_client) == 1 and new_client[0]["source_type"] == "service_case_client", new_client
    assert not old_client, old_client
    assert not old_supplier, old_supplier
    assert len(new_supplier_a) == 1 and len(new_supplier_b) == 1, (new_supplier_a, new_supplier_b)
    assert float(new_client[0]["amount_original"]) == 330.0
    assert float(new_supplier_a[0]["amount_original"]) == 170.0
    assert float(new_supplier_b[0]["amount_original"]) == 50.0
    assert all(int(r.get("is_locked") or 0) == 1 for r in new_client + new_supplier_a + new_supplier_b)

    audit = "\n".join(str(r) for r in AuditRepository().get_all())
    assert "تعديل ملف خدمة" in audit and "تصحيح مورد" in audit, audit

    rc = ReportingCenterService()
    profit = rc.build_report(REPORT_PROFIT, period=PERIOD_ALL)
    services = rc.build_report(REPORT_SERVICES, period=PERIOD_ALL)
    joined_profit = "\n".join(str(row) for row in profit.rows)
    joined_services = "\n".join(str(row) for row in services.rows)
    assert "عميل خدمة معدل" in joined_profit and "110" in joined_profit, joined_profit
    assert "مورد تأشيرات جديد" in joined_services or "مورد نقل جديد" in joined_services, joined_services

    service_repo.reverse(ref, reason="إلغاء بعد اختبار التعديل")
    after_reverse = service_repo.get_by_reference(ref)
    assert after_reverse["status"] == "reversed"
    try:
        service_repo.update(ref, {
            "client_company_name": "عميل خدمة معدل",
            "supplier_company_name": "مورد تأشيرات جديد",
            "person_name": "سليم",
            "service_type": "تأشيرة سياحية",
            "sale_amount_original": 100,
            "cost_amount_original": 90,
            "currency_original": "USD",
            "date": "2026-07-13",
            "notes": "غير مسموح",
        }, edit_reason="محاولة بعد العكس")
        raise AssertionError("reversed supplier service was editable")
    except Exception as exc:
        assert "معكوس" in str(exc), str(exc)

    print("linked_supplier_service_edit_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
