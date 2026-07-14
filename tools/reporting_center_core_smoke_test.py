# -*- coding: utf-8 -*-
"""Smoke test for Phase 83 Professional Reporting Center."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_reporting_center_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)
try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import AuditRepository, ExpenseRepository, ServiceCaseRepository, ThirdPartyPaymentRepository
    from reports.reporting_center import (
        PERIOD_ALL,
        REPORT_AGING,
        REPORT_AUDIT,
        REPORT_COMPANY_BALANCES,
        REPORT_DEFINITIONS,
        REPORT_PROFIT,
        REPORT_SERVICES,
        REPORT_THIRD_PARTY,
        ReportingCenterService,
        export_report_csv,
        export_report_html,
    )

    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})
    expenses = ExpenseRepository()
    expenses.add("شركة العميل", 200, "incoming", "2026-07-01", "بيع خدمة", "USD", 1, person_name="أحمد", service_type="حجز")
    expenses.add("شركة العميل", 50, "outgoing", "2026-07-02", "تسديد جزئي", "USD", 1, service_type="تسديد")
    ThirdPartyPaymentRepository().add_payment_on_behalf("الشركة الدافعة", "شركة العميل", 25, "USD", "2026-07-03", "اختبار سدد عني", 1)
    ServiceCaseRepository().add({
        "client_company_name": "بلو ستار",
        "supplier_company_name": "سيف الشام",
        "person_name": "طارق",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 150,
        "cost_amount_original": 120,
        "currency_original": "USD",
        "date": "2026-07-04",
        "notes": "اختبار تقرير الخدمات",
    })
    AuditRepository().log(1, "admin", "اختبار تقرير", "reports", 1, "reporting center smoke")

    service = ReportingCenterService()
    report_ids = [REPORT_COMPANY_BALANCES, REPORT_AGING, REPORT_PROFIT, REPORT_SERVICES, REPORT_THIRD_PARTY, REPORT_AUDIT]
    for report_id in report_ids:
        report = service.build_report(report_id, period=PERIOD_ALL)
        assert report.title == REPORT_DEFINITIONS[report_id]["title"]
        assert report.columns, report_id
        assert isinstance(report.summary, list), report_id
        html_path = Path(export_report_html(report))
        csv_path = Path(export_report_csv(report))
        assert html_path.exists() and csv_path.exists(), report_id
        html = html_path.read_text(encoding="utf-8")
        assert "مركز التقارير الموحّد" in html
        assert "نظام هوى الشام" in html
        assert "unicode-bidi:isolate" in html
        assert "#220A3F70" not in html
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        assert report.columns[0]["label"] in csv_text

    balances = service.build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
    assert any(r.get("company") == "شركة العميل" for r in balances.rows)
    aging = service.build_report(REPORT_AGING, period=PERIOD_ALL)
    assert any(r.get("bucket") in {"0 - 7 أيام", "8 - 30 يوم", "31 - 60 يوم", "أكثر من 60 يوم"} for r in aging.rows)
    profit = service.build_report(REPORT_PROFIT, period=PERIOD_ALL)
    assert any("تأشيرة" in str(r.get("service")) for r in profit.rows)
    services = service.build_report(REPORT_SERVICES, period=PERIOD_ALL)
    assert any(r.get("reference", "").startswith("SVC-") for r in services.rows)
    tpp = service.build_report(REPORT_THIRD_PARTY, period=PERIOD_ALL)
    assert any(r.get("reference", "").startswith("TPP-") for r in tpp.rows)
    audit = service.build_report(REPORT_AUDIT, period=PERIOD_ALL)
    assert any("اختبار تقرير" in str(r.get("action")) for r in audit.rows)

    app_layout = (ROOT / "views" / "app_layout.py").read_text(encoding="utf-8")
    view_src = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")
    assert "ReportsCenterMobileView" in app_layout and "reports" in app_layout
    assert "REPORT_COMPANY_BALANCES" in view_src and "export_report_html" in view_src and "export_report_csv" in view_src
    print("reporting_center_core_smoke_test passed", flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

# Some imported mobile/report helpers can leave runtime threads alive in CI.
# This smoke test is a CLI verifier; force a clean process exit.
sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
