# -*- coding: utf-8 -*-
"""Operational visibility and balance regression test for reversed services.

A reversed intermediary service case or direct/quick service must remain in the
raw ledger for audit, while both the original and reversal rows disappear from
company screens, statements, operational reports, searches and balance totals.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_reversed_visibility_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import DirectServiceRepository, ExpenseRepository, ServiceCaseRepository
    from reports.account_statement import build_rows, export_account_statement_html
    from reports.reporting_center import (
        PERIOD_ALL,
        REPORT_COMPANY_BALANCES,
        REPORT_LOCKED_ENTRIES,
        REPORT_OPERATION_SUMMARY,
        REPORT_PROFIT,
        REPORT_REVERSALS,
        REPORT_SERVICES,
        ReportingCenterService,
    )

    UserSession.login({"id": 1, "username": "admin", "role": "admin"})
    expenses = ExpenseRepository()

    # A normal row is the baseline that must survive all service reversals.
    expenses.add(
        company_name="شركة العميل",
        amount=10,
        type_val="incoming",
        date="2026-07-01",
        notes="قيد عادي مرجعي",
        currency_code="USD",
        user_id=1,
    )

    service_repo = ServiceCaseRepository()
    service = service_repo.add({
        "client_company_name": "شركة العميل",
        "person_name": "مسافر خدمة معكوسة",
        "service_type": "متعدد الخدمات",
        "currency_original": "USD",
        "date": "2026-07-02",
        "notes": "اختبار إخفاء كامل",
        "components": [
            {
                "service_type": "تأشيرة سياحية",
                "supplier_company_name": "مورد التأشيرة",
                "sale_amount_original": 100,
                "cost_amount_original": 70,
            },
            {
                "service_type": "نقل بري",
                "supplier_company_name": "مورد النقل",
                "sale_amount_original": 50,
                "cost_amount_original": 30,
            },
        ],
    })
    service_ref = service["reference"]

    before_client = expenses.get_by_company("شركة العميل", convert_to_display=False)
    assert any(r.get("source_ref") == service_ref for r in before_client), before_client

    try:
        service_repo.reverse(service_ref, reason="")
        raise AssertionError("service reversal accepted without a reason")
    except Exception as exc:
        assert "سبب" in str(exc), str(exc)

    service_repo.reverse(service_ref, reason="إلغاء العملية الاختبارية")
    try:
        service_repo.reverse(service_ref, reason="محاولة عكس ثانية")
        raise AssertionError("service case was reversed twice")
    except Exception as exc:
        assert "معكوس" in str(exc) or "عكس" in str(exc), str(exc)

    # All linked rows disappear from every operational company ledger.
    for company in ("شركة العميل", "مورد التأشيرة", "مورد النقل"):
        visible = expenses.get_by_company(company, convert_to_display=False)
        assert not any(r.get("source_ref") == service_ref for r in visible), (company, visible)

    raw_service_rows = [
        r for r in expenses.get_all(convert_to_display=False, include_reversed=True)
        if r.get("source_ref") == service_ref
    ]
    assert len(raw_service_rows) == 6, raw_service_rows  # 3 original + 3 reversal
    assert len([r for r in raw_service_rows if r.get("source_type") == "service_case_reversal"]) == 3

    # Direct/quick service follows the same operational hiding rule.
    direct_repo = DirectServiceRepository()
    direct = direct_repo.add({
        "company_name": "شركة سريعة",
        "person_name": "مسافر خدمة سريعة",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 200,
        "cost_amount_original": 150,
        "supplier_company_name": "مورد سريع",
        "currency_original": "USD",
        "date": "2026-07-03",
        "notes": "خدمة سريعة للاختبار",
    })
    direct_ref = direct["reference"]
    try:
        direct_repo.reverse(direct_ref, reason="")
        raise AssertionError("direct service reversal accepted without a reason")
    except Exception as exc:
        assert "سبب" in str(exc), str(exc)
    direct_repo.reverse(direct_ref, reason="إلغاء الخدمة السريعة", date="2026-07-04")
    try:
        direct_repo.reverse(direct_ref, reason="محاولة عكس ثانية", date="2026-07-04")
        raise AssertionError("direct service was reversed twice")
    except Exception as exc:
        assert "معكوس" in str(exc) or "عكس" in str(exc), str(exc)

    for company in ("شركة سريعة", "مورد سريع"):
        visible = expenses.get_by_company(company, convert_to_display=False)
        assert not any(r.get("source_ref") == direct_ref for r in visible), (company, visible)

    raw_direct_rows = [
        r for r in expenses.get_all(convert_to_display=False, include_reversed=True)
        if r.get("source_ref") == direct_ref
    ]
    assert len(raw_direct_rows) == 4, raw_direct_rows  # 2 original + 2 reversal

    # Search is operational by default, while audit access remains explicit.
    assert not expenses.search_company_ledger("مسافر خدمة معكوسة", limit=50)
    assert expenses.search_company_ledger("مسافر خدمة معكوسة", limit=50, include_reversed=True)
    assert not expenses.search_company_ledger("مسافر خدمة سريعة", limit=50)

    # Balances exclude the complete reversal groups instead of merely netting
    # inflated incoming/outgoing totals against each other.
    summary = expenses.get_summary(convert_to_display=False)
    assert abs(float(summary["total_incoming"]) - 10.0) < 0.001, summary
    assert abs(float(summary["total_outgoing"])) < 0.001, summary
    assert abs(float(summary["net"]) - 10.0) < 0.001, summary

    # Rendering must defend itself even when a caller passes raw audit rows.
    raw_client = [
        r for r in expenses.get_all(convert_to_display=False, include_reversed=True)
        if r.get("company_name") == "شركة العميل"
    ]
    statement_rows, statement_totals = build_rows(raw_client, "USD")
    rendered = "\n".join(str(r) for r in statement_rows)
    assert service_ref not in rendered and "مسافر خدمة معكوسة" not in rendered, rendered
    assert len(statement_rows) == 1, statement_rows
    assert abs(float(statement_totals["net_usd"]) - 10.0) < 0.001, statement_totals
    html_path = export_account_statement_html("شركة العميل", raw_client, output_path=str(tmp / "statement.html"))
    html = Path(html_path).read_text(encoding="utf-8")
    assert service_ref not in html and "مسافر خدمة معكوسة" not in html, html

    reports = ReportingCenterService()
    for report_id in (
        REPORT_COMPANY_BALANCES,
        REPORT_SERVICES,
        REPORT_PROFIT,
        REPORT_LOCKED_ENTRIES,
        REPORT_OPERATION_SUMMARY,
    ):
        report = reports.build_report(report_id, period=PERIOD_ALL)
        joined = "\n".join(str(row) for row in report.rows)
        assert service_ref not in joined, (report_id, joined)
        assert direct_ref not in joined, (report_id, joined)
        assert "مسافر خدمة معكوسة" not in joined, (report_id, joined)
        assert "مسافر خدمة سريعة" not in joined, (report_id, joined)

    company_report = reports.build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
    company_row = next(r for r in company_report.rows if r.get("company") == "شركة العميل")
    assert company_row.get("count") == 1, company_row

    # Only the dedicated audit report may expose the reversed operations.
    reversal_report = reports.build_report(REPORT_REVERSALS, period=PERIOD_ALL)
    reversal_text = "\n".join(str(row) for row in reversal_report.rows)
    assert service_ref in reversal_text, reversal_text
    assert direct_ref in reversal_text, reversal_text

    print("reversed_service_operational_visibility_smoke_test passed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
