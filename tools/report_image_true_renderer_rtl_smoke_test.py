# -*- coding: utf-8 -*-
"""Regression guards for PNG report rendering on Android.

PNG exports must be generated from report data, not from the current Flet page.
They also must not rely on libraqm being present in Android Pillow; without an
RTL fallback Arabic labels may appear visually reversed in exported images.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

tmp = Path(tempfile.mkdtemp(prefix="hawaa_png_true_renderer_"))
os.environ["HAWAA_DATA_DIR"] = str(tmp)

try:
    from database.migrations import ensure_db
    ensure_db()
    from database import ExpenseRepository
    import reports.image_export as img_export
    from reports.image_export import export_statement_image, export_report_image, PAGE_W
    from reports.reporting_center import ReportingCenterService, REPORT_COMPANY_BALANCES, PERIOD_ALL
    from PIL import Image

    source = (ROOT / "reports" / "image_export.py").read_text(encoding="utf-8")
    forbidden = ["screenshot", "capture", "page.screenshot", "ImageOps.mirror", "ImageOps.flip"]
    for token in forbidden:
        assert token not in source, f"PNG export must be data-rendered, not UI/screenshot based: {token}"

    # Simulate Android Pillow without libraqm and make sure fallback reshaping is active.
    old_raqm = img_export._HAS_RAQM
    img_export._HAS_RAQM = False
    try:
        visual = img_export._display_text("كشف مطابقة - أدهم", rtl=True)
        assert visual != "كشف مطابقة - أدهم", "Arabic fallback must transform text when libraqm is absent"
        assert any("\ufe80" <= ch <= "\ufefc" for ch in visual), "fallback should use Arabic presentation forms"

        repo = ExpenseRepository()
        repo.add("أدهم", 250, "outgoing", "2026-05-26", "تكلفة تذكرة سفر للزبون محمد", "USD", 1, person_name="محمد", service_type="تذكرة سفر")
        records = repo.get_by_company("أدهم", convert_to_display=False)
        statement_png = Path(export_statement_image("أدهم", records, reconciliation=True))
        assert statement_png.exists() and statement_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        with Image.open(statement_png) as im:
            assert im.width == PAGE_W, f"statement PNG must use report canvas width, not phone screenshot width: {im.size}"
            assert im.height < 9000, f"statement PNG unexpectedly huge: {im.size}"

        report = ReportingCenterService().build_report(REPORT_COMPANY_BALANCES, period=PERIOD_ALL)
        report_png = Path(export_report_image(report))
        assert report_png.exists() and report_png.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        with Image.open(report_png) as im:
            assert im.width == PAGE_W, f"report PNG must use report canvas width, not phone screenshot width: {im.size}"
    finally:
        img_export._HAS_RAQM = old_raqm
    print("report_image_true_renderer_rtl_smoke_test passed", flush=True)
finally:
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        sys.stdout.flush(); sys.stderr.flush()
    except Exception:
        pass
