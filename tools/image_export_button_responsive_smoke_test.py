# -*- coding: utf-8 -*-
"""Static/runtime guard for PNG buttons not appearing dead on Android."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

company_view = (ROOT / "views" / "company_details_mobile_view.py").read_text(encoding="utf-8")
reports_view = (ROOT / "views" / "reports_center_mobile_view.py").read_text(encoding="utf-8")

assert "on_click=self._on_share_statement_image" in company_view
assert "def _on_share_statement_image" in company_view
assert "run_async_task(self._page, self._share_statement_image_async)" in company_view
assert "asyncio.to_thread(lambda: export_statement_image" in company_view

assert "def _on_export_png" in reports_view
assert "run_async_task(self._page, self._export_png_async)" in reports_view
assert "asyncio.to_thread(lambda: export_report_image" in reports_view

print("image_export_button_responsive_smoke_test passed")
