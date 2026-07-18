# -*- coding: utf-8 -*-
"""Regression guard for Android PNG export buttons.

The PNG path used to look unresponsive on phones because it depended on an
extra scheduling wrapper and could allocate very tall bitmaps.  This test keeps
button handlers explicitly scheduled from the unified export menu, image height bounded, and text drawing tolerant of
Android Pillow builds without libraqm/default-font RTL support.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

company_view = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
reports_view = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")
image_export = (ROOT / "reports" / "image_export.py").read_text(encoding="utf-8")

assert "run_async_task(self._page, self._share_statement_image_async, ev)" in company_view, "company PNG menu action must schedule the async renderer"
assert "جارٍ إنشاء صورة كشف المطابقة" in company_view, "company PNG action must provide immediate feedback"
assert "run_async_task(self._page, self._export_png_async, ev)" in reports_view, "report PNG menu action must schedule the async renderer"
assert "جارٍ إنشاء صورة PNG للتقرير" in reports_view, "report PNG action must provide immediate feedback"
assert "max_rows: int = 60" in image_export, "statement PNG must be capped for Android memory"
assert "max_rows: int = 40" in image_export, "report PNG must be capped for Android memory"
assert "optimize=False" in image_export and "compress_level=3" in image_export, "PNG save must be fast on Android"
assert "except Exception:" in image_export and "kwargs.pop(\"direction\", None)" in image_export, "RTL draw fallback required"

# Runtime check: a large statement/report still produces a compact PNG, not a
# giant bitmap likely to be killed by Android.
tmp = Path(tempfile.mkdtemp(prefix="hawaa_png_regression_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)
try:
    from database.migrations import ensure_db
    ensure_db()
    from database import ExpenseRepository
    from reports.image_export import export_statement_image, export_report_image
    from reports.reporting_center import ReportingCenterService, REPORT_COMPANY_BALANCES, PERIOD_ALL

    repo = ExpenseRepository()
    for i in range(120):
        repo.add("شركة ضغط الصورة", 10 + i, "incoming" if i % 2 == 0 else "outgoing", f"2026-07-{(i % 28) + 1:02d}", f"حركة طويلة رقم {i}", "USD", 1, person_name=f"شخص {i}", service_type="اختبار")
    records = repo.get_by_company("شركة ضغط الصورة", convert_to_display=False)
    statement = Path(export_statement_image("شركة ضغط الصورة", records, reconciliation=True))
    assert statement.exists() and statement.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert statement.stat().st_size < 2_500_000, f"statement PNG too large for mobile quick share: {statement.stat().st_size}"

    report = ReportingCenterService().build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
    report_png = Path(export_report_image(report))
    assert report_png.exists() and report_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert report_png.stat().st_size < 2_500_000, f"report PNG too large for mobile quick share: {report_png.stat().st_size}"
    print("image_export_android_responsiveness_regression_test passed", flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        sys.stdout.flush(); sys.stderr.flush()
    except Exception:
        pass

# Pillow/Flet helper resources can keep inherited descriptors open in a long
# quality-gate session. This file is a CLI verifier, so terminate explicitly
# after all assertions and cleanup complete.
try:
    sys.stdout.flush(); sys.stderr.flush()
except Exception:
    pass
os._exit(0)
