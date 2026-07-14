# -*- coding: utf-8 -*-
"""Smoke test for Phase 88 PNG image exports for statements and reports."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp(prefix="hawaa_report_image_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)


def _assert_png(path: Path) -> None:
    assert path.exists(), path
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n"), path
    assert len(data) > 2048, f"PNG too small: {path}"


try:
    from database.migrations import ensure_db
    ensure_db()
    from auth.session import UserSession
    from database import ExpenseRepository, ServiceCaseRepository
    from reports.image_export import export_report_image, export_statement_image
    from reports.reporting_center import PERIOD_ALL, REPORT_COMPANY_BALANCES, ReportingCenterService

    UserSession.login({"id": 1, "username": "admin", "role": "admin", "full_name": "المدير العام"})
    repo = ExpenseRepository()
    repo.add("شركة الصورة", 300, "incoming", "2026-07-01", "بيع خدمة تأشيرة", "USD", 1, person_name="أحمد", service_type="تأشيرة")
    repo.add("شركة الصورة", 100, "outgoing", "2026-07-02", "دفعة مورد", "USD", 1, service_type="سداد")
    ServiceCaseRepository().add({
        "client_company_name": "شركة الصورة",
        "supplier_company_name": "مورد الصورة",
        "person_name": "ليث",
        "service_type": "نقل بري",
        "sale_amount_original": 80,
        "cost_amount_original": 55,
        "currency_original": "USD",
        "date": "2026-07-03",
        "notes": "اختبار صورة تقرير",
    })

    records = repo.get_by_company("شركة الصورة", convert_to_display=False)
    statement_png = Path(export_statement_image("شركة الصورة", records, reconciliation=True))
    detail_png = Path(export_statement_image("شركة الصورة", records, reconciliation=False))
    _assert_png(statement_png)
    _assert_png(detail_png)

    service = ReportingCenterService()
    report = service.build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
    report_png = Path(export_report_image(report))
    _assert_png(report_png)

    company_view = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
    report_view = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "export_statement_image" in company_view and "صورة" in company_view
    assert "export_report_image" in report_view and "PNG" in report_view
    assert "Pillow" in pyproject
    print("report_image_export_smoke_test passed", flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)

sys.stdout.flush()
sys.stderr.flush()
os._exit(0)
