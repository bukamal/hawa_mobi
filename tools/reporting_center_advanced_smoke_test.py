# -*- coding: utf-8 -*-
"""Smoke test for Phase 84 advanced operational/audit reports."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_reporting_advanced_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)
try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import ExpenseRepository, ServiceCaseRepository, ThirdPartyPaymentRepository
    from reports.reporting_center import (
        PERIOD_ALL,
        REPORT_DEFINITIONS,
        REPORT_LOCKED_ENTRIES,
        REPORT_LOW_MARGIN,
        REPORT_OPEN_SERVICES,
        REPORT_OPERATION_SUMMARY,
        REPORT_REVERSALS,
        ReportingCenterService,
        export_report_csv,
        export_report_html,
    )

    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})
    expenses = ExpenseRepository()
    service_cases = ServiceCaseRepository()
    third_party = ThirdPartyPaymentRepository()

    expenses.add("قيد عادي", 75, "incoming", "2026-07-01", "قيد غير مقفل", "USD", 1, person_name="عميل عادي", service_type="غير محدد")
    open_ref = service_cases.add({
        "client_company_name": "عميل مفتوح",
        "supplier_company_name": "مورد مفتوح",
        "person_name": "مسافر مفتوح",
        "service_type": "تذكرة سفر",
        "sale_amount_original": 300,
        "cost_amount_original": 250,
        "currency_original": "USD",
        "date": "2026-07-02",
        "notes": "خدمة مفتوحة للاختبار",
    })["reference"]
    low_ref = service_cases.add({
        "client_company_name": "عميل هامش منخفض",
        "supplier_company_name": "مورد هامش منخفض",
        "person_name": "مسافر هامش",
        "service_type": "تأشيرة سياحية",
        "sale_amount_original": 100,
        "cost_amount_original": 97,
        "currency_original": "USD",
        "date": "2026-07-03",
        "notes": "هامش منخفض للاختبار",
    })["reference"]
    reversed_ref = service_cases.add({
        "client_company_name": "عميل معكوس",
        "supplier_company_name": "مورد معكوس",
        "person_name": "مسافر معكوس",
        "service_type": "نقل بري",
        "sale_amount_original": 80,
        "cost_amount_original": 60,
        "currency_original": "USD",
        "date": "2026-07-04",
        "notes": "سيتم عكسها",
    })["reference"]
    service_cases.reverse(reversed_ref)
    tpp_ref = third_party.add_payment_on_behalf("شركة دفعت", "شركة دُفع لها", 40, "USD", "2026-07-05", "سداد للاختبار", 1)["reference"]
    third_party.reverse_payment_on_behalf(tpp_ref, user_id=1, date="2026-07-06")

    service = ReportingCenterService()
    advanced_ids = [REPORT_OPEN_SERVICES, REPORT_LOW_MARGIN, REPORT_LOCKED_ENTRIES, REPORT_REVERSALS, REPORT_OPERATION_SUMMARY]
    for report_id in advanced_ids:
        report = service.build_report(report_id, period=PERIOD_ALL)
        assert report.title == REPORT_DEFINITIONS[report_id]["title"], report_id
        assert report.columns, report_id
        assert isinstance(report.rows, list), report_id
        html_path = Path(export_report_html(report))
        csv_path = Path(export_report_csv(report))
        assert html_path.exists() and csv_path.exists(), report_id
        html = html_path.read_text(encoding="utf-8")
        assert report.title in html
        assert "مركز التقارير الموحّد" in html
        assert "#220A3F70" not in html
        assert "unicode-bidi:isolate" in html
        csv_text = csv_path.read_text(encoding="utf-8-sig")
        assert report.columns[0]["label"] in csv_text

    open_services = service.build_report(REPORT_OPEN_SERVICES, period=PERIOD_ALL)
    assert any(r.get("reference") == open_ref for r in open_services.rows)
    assert any(r.get("reference") == low_ref for r in open_services.rows)
    assert not any(r.get("reference") == reversed_ref for r in open_services.rows)

    low_margin = service.build_report(REPORT_LOW_MARGIN, period=PERIOD_ALL)
    assert any(r.get("reference") == low_ref and r.get("risk") == "هامش منخفض" for r in low_margin.rows)
    assert not any(r.get("reference") == open_ref for r in low_margin.rows)

    locked = service.build_report(REPORT_LOCKED_ENTRIES, period=PERIOD_ALL)
    assert any(str(r.get("reference")).startswith("SVC-") for r in locked.rows)
    assert any(str(r.get("reference")).startswith("TPP-") for r in locked.rows)
    assert not any(r.get("company") == "قيد عادي" for r in locked.rows)

    reversals = service.build_report(REPORT_REVERSALS, period=PERIOD_ALL)
    assert any("عكس" in str(r.get("operation")) or "reversal" in str(r.get("operation")) for r in reversals.rows)
    assert any(str(r.get("reference")).startswith("TPP-") for r in reversals.rows)
    assert any(str(r.get("reference")).startswith("REV-SVC-") or "SVC-" in str(r.get("notes")) for r in reversals.rows)

    op_summary = service.build_report(REPORT_OPERATION_SUMMARY, period=PERIOD_ALL)
    ops = "\n".join(str(r.get("operation")) for r in op_summary.rows)
    assert "قيد عادي" in ops
    assert "خدمة وسيطة" in ops
    assert "سداد بالنيابة" in ops

    view_src = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")
    for const_name in ["REPORT_OPEN_SERVICES", "REPORT_LOW_MARGIN", "REPORT_LOCKED_ENTRIES", "REPORT_REVERSALS", "REPORT_OPERATION_SUMMARY"]:
        assert const_name in view_src

    print("reporting_center_advanced_smoke_test passed", flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
