# -*- coding: utf-8 -*-
"""Guard supplier-only direct-service workflow from company cards.

When the user taps "مباشرة" on a company card, that company is the supplier
/source of the service.  The workflow must not create a receivable against the
same company; it should post only the supplier cost as payable and keep sale,
cost and profit in direct-service metadata.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_direct_supplier_only_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import DirectServiceRepository, ExpenseRepository, AuditRepository
    from reports.reporting_center import PERIOD_ALL, REPORT_DIRECT_SERVICES, REPORT_PROFIT, ReportingCenterService

    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})

    repo = DirectServiceRepository()
    result = repo.add({
        "company_name": "أدهم",
        "person_name": "محمد مباشر",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 200,
        "cost_amount_original": 150,
        "supplier_company_name": "أدهم",
        "currency_original": "USD",
        "date": "2026-07-20",
        "notes": "اختبار مباشر عبر مورد",
        "supplier_only": True,
    })
    ref = result["reference"]
    assert result["client_expense_id"] in (None, ""), result
    assert result["supplier_expense_id"], result
    assert abs(float(result["profit_base"]) - 50.0) < 0.001, result

    expenses = ExpenseRepository()
    rows = [r for r in expenses.get_by_company("أدهم", convert_to_display=False) if r.get("source_ref") == ref]
    assert len(rows) == 1, rows
    row = rows[0]
    assert row["source_type"] == "direct_service_supplier", row
    assert row["type"] == "outgoing", row
    assert float(row["amount_original"]) == 150.0, row
    assert "direct_service_client" not in "\n".join(str(r) for r in rows), rows

    service = repo.get_by_reference(ref)
    assert not service.get("client_expense_id"), service
    assert service.get("supplier_company_name") == "أدهم", service
    assert service.get("company_name") == "أدهم", service

    updated = repo.update(ref, {
        "company_name": "أدهم",
        "person_name": "محمد مباشر",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 230,
        "cost_amount_original": 160,
        "supplier_company_name": "أدهم",
        "currency_original": "USD",
        "date": "2026-07-21",
        "notes": "تصحيح مباشر عبر المورد",
        "supplier_only": True,
    }, edit_reason="تصحيح تكلفة المورد")
    assert updated["client_expense_id"] in (None, ""), updated
    assert updated["supplier_expense_id"] == result["supplier_expense_id"], updated
    assert abs(float(updated["profit_base"]) - 70.0) < 0.001, updated

    rows_after = [r for r in expenses.get_by_company("أدهم", convert_to_display=False) if r.get("source_ref") == ref and r.get("source_type") == "direct_service_supplier"]
    assert len(rows_after) == 1, rows_after
    assert rows_after[0]["type"] == "outgoing" and float(rows_after[0]["amount_original"]) == 160.0, rows_after

    rc = ReportingCenterService()
    direct_report = rc.build_report(REPORT_DIRECT_SERVICES, period=PERIOD_ALL)
    joined = "\n".join(str(row) for row in direct_report.rows)
    assert "محمد مباشر" in joined and "أدهم" in joined and "70" in joined, joined
    profit_report = rc.build_report(REPORT_PROFIT, period=PERIOD_ALL)
    assert "محمد مباشر" in "\n".join(str(row) for row in profit_report.rows), profit_report.rows

    rev = repo.reverse(ref, reason="إلغاء مباشر عبر المورد", date="2026-07-22")
    assert rev["client_reversal_expense_id"] in (None, ""), rev
    assert rev["supplier_reversal_expense_id"], rev
    rev_rows = [r for r in expenses.get_by_company("أدهم", convert_to_display=False, include_reversed=True) if r.get("source_ref") == ref and r.get("source_type") == "direct_service_reversal"]
    assert len(rev_rows) == 1 and rev_rows[0]["type"] == "incoming", rev_rows

    audit = "\n".join(str(r) for r in AuditRepository().get_all())
    assert "تعديل خدمة مباشرة" in audit and "عكس خدمة مباشرة" in audit, audit

    print("direct_supplier_only_service_workflow_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
