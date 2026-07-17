# -*- coding: utf-8 -*-
"""Smoke test for Phase 67 intermediary service-case workflow."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_service_case_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)
try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import ExpenseRepository, ServiceCaseRepository
    from reports.account_statement import export_reconciliation_statement_html, export_service_profit_report_html

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    service_repo = ServiceCaseRepository()
    result = service_repo.add({
        "client_company_name": "بلو ستار",
        "supplier_company_name": "سيف الشام",
        "person_name": "أحمد محمد",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 150,
        "cost_amount_original": 120,
        "currency_original": "USD",
        "date": "2026-07-12",
        "notes": "اختبار",
    })
    assert result["reference"].startswith("SVC-"), result
    repo = ExpenseRepository()
    client_rows = repo.get_by_company("بلو ستار", convert_to_display=False)
    supplier_rows = repo.get_by_company("سيف الشام", convert_to_display=False)
    assert len(client_rows) == 1 and len(supplier_rows) == 1
    assert client_rows[0]["source_type"] == "service_case_client"
    assert supplier_rows[0]["source_type"] == "service_case_supplier"
    assert client_rows[0]["print_description"] == "تأشيرة سياحية - أحمد محمد"
    assert supplier_rows[0]["print_description"].startswith("تكلفة تأشيرة سياحية")
    try:
        repo.delete(client_rows[0]["id"], 1)
        raise AssertionError("locked service-case row was deletable")
    except Exception as exc:
        assert "لا يُحذف" in str(exc) or "مرتبط" in str(exc)
    found = repo.search_company_ledger("أحمد محمد", limit=20)
    assert {r["company_name"] for r in found} >= {"بلو ستار", "سيف الشام"}
    rec = export_reconciliation_statement_html("بلو ستار", client_rows)
    html = Path(rec).read_text(encoding="utf-8")
    assert "كشف حساب للمطابقة" in html
    assert "سيف الشام" not in html or "الشركة المرتبطة" not in html  # do not expose internal report structure
    profit = export_service_profit_report_html(service_repo.list_cases())
    assert "تقرير أرباح الخدمات الداخلي" in Path(profit).read_text(encoding="utf-8")
    reversed_payload = service_repo.reverse(result["reference"], reason="إلغاء ملف الاختبار")
    assert reversed_payload["reversal_ref"].startswith("REV-")
    print("service_case_workflow_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
