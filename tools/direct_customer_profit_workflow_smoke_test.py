# -*- coding: utf-8 -*-
"""Smoke test for Phase 90 direct customer profit workflow."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_direct_profit_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import DirectServiceRepository, ExpenseRepository
    from reports.reporting_center import PERIOD_ALL, REPORT_DIRECT_SERVICES, REPORT_PROFIT, REPORT_SERVICES, ReportingCenterService

    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})

    # A normal entry with a person/service should affect the ledger only.  It
    # must not create profit metadata implicitly.
    ExpenseRepository().add("حساب مباشر", 999, "incoming", "2026-07-14", "قيد عادي للزبون", "USD", 1, person_name="زبون عادي", service_type="تذكرة سفر")

    result = DirectServiceRepository().add({
        "company_name": "حساب مباشر",
        "person_name": "أحمد مباشر",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 150,
        "cost_amount_original": 120,
        "supplier_company_name": "مورد مباشر",
        "currency_original": "USD",
        "date": "2026-07-14",
        "notes": "اختبار خدمة مباشرة",
    })
    assert result["reference"].startswith("DIR-"), result
    assert abs(float(result["profit_base"]) - 30.0) < 0.0001, result

    repo = ExpenseRepository()
    client_rows = repo.get_by_company("حساب مباشر", convert_to_display=False)
    supplier_rows = repo.get_by_company("مورد مباشر", convert_to_display=False)
    direct_client = [r for r in client_rows if r.get("source_type") == "direct_service_client"]
    assert len(direct_client) == 1, client_rows
    assert len(supplier_rows) == 1 and supplier_rows[0]["source_type"] == "direct_service_supplier", supplier_rows
    assert direct_client[0]["is_locked"] == 1
    assert supplier_rows[0]["is_locked"] == 1
    try:
        repo.delete(direct_client[0]["id"], 1)
        raise AssertionError("direct service row was deletable")
    except Exception as exc:
        assert "لا يُحذف" in str(exc) or "مرتبط" in str(exc)

    direct_services = DirectServiceRepository().list_services()
    assert len(direct_services) == 1
    assert direct_services[0]["person_name"] == "أحمد مباشر"

    rc = ReportingCenterService()
    direct_report = rc.build_report(REPORT_DIRECT_SERVICES, period=PERIOD_ALL)
    assert any("أحمد مباشر" == row.get("person") for row in direct_report.rows), direct_report.rows
    assert any(item.get("value") and "30" in item.get("value") for item in direct_report.summary), direct_report.summary

    profit_report = rc.build_report(REPORT_PROFIT, period=PERIOD_ALL)
    joined = "\n".join(str(row) for row in profit_report.rows)
    assert "أحمد مباشر" in joined and "زبون عادي" not in joined, joined

    services_report = rc.build_report(REPORT_SERVICES, period=PERIOD_ALL)
    assert "مباشرة" in "\n".join(str(row) for row in services_report.rows)

    print("direct_customer_profit_workflow_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
