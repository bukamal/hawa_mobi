# -*- coding: utf-8 -*-
"""Guard all Android report actions against missing ft.Share runtime service.

The APK's Flet runtime can omit ft.Share.  Report buttons such as print,
share, WhatsApp, backup and CSV must therefore go through the same fallback
pipeline and must never instantiate Flet Share directly from views.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

share_source = (ROOT / "reports" / "share.py").read_text(encoding="utf-8")
file_service_source = (ROOT / "services" / "file_export_service.py").read_text(
    encoding="utf-8"
)
company_view_source = (ROOT / "views" / "company_details_mobile_view.py").read_text(
    encoding="utf-8"
)
settings_view_source = (ROOT / "views" / "settings_mobile_view.py").read_text(
    encoding="utf-8"
)

assert 'getattr(ft, "Share", None)' in share_source, (
    "reports/share.py must feature-detect ft.Share"
)
assert "ft.Share()" not in share_source, (
    "reports/share.py must not call ft.Share() directly"
)
assert "copy_to_public_downloads" in share_source, "missing public Downloads fallback"
assert "_show_manual_export_dialog" in share_source, "missing manual fallback dialog"
assert "share_text_to_whatsapp_async" in share_source, "missing WhatsApp text fallback"

assert "reports.share" in file_service_source, (
    "FileExportService must delegate to reports.share"
)
assert "open_file_async" in file_service_source, (
    "print/open path must use unified export service"
)
assert "share_file_async" in file_service_source, (
    "share path must use unified export service"
)

assert "FileExportService.open_file_async" in company_view_source, (
    "print button must use FileExportService.open_file_async"
)
assert "share_file_async" in company_view_source, (
    "share/WhatsApp buttons must use fallback share_file_async"
)
assert "ft.Share" not in company_view_source, (
    "company view must not use ft.Share directly"
)
assert "page.share" not in company_view_source, (
    "company view must not use page.share directly"
)
assert "page.share_files" not in company_view_source, (
    "company view must not use page.share_files directly"
)

assert "FileExportService.share_file_async" in settings_view_source, (
    "backup/CSV buttons must use FileExportService.share_file_async"
)
assert "ft.Share" not in settings_view_source, (
    "settings view must not use ft.Share directly"
)

for path in ROOT.rglob("*.py"):
    rel = path.relative_to(ROOT)
    if rel.parts == ("reports", "share.py"):
        continue
    if path.name.startswith("report_action_share_print_whatsapp_smoke_test"):
        continue
    source = path.read_text(encoding="utf-8", errors="ignore")
    if "ft.Share" in source and "tools" not in str(rel):
        raise AssertionError(
            f"Forbidden ft.Share reference outside reports/share.py: {rel}"
        )

print("✅ report_action_share_print_whatsapp_smoke_test passed")
