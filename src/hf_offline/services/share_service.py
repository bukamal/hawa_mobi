"""Report sharing & printing — one code path, three delivery channels.

Delivery order (the first one that works wins):

1. **native**  — when the app is bundled with the ``flet-native-files``
   extension (Android share sheet / iOS share), the saved HTML file goes
   straight to the OS share sheet.
2. **browser** — on desktop (and anywhere the native bridge is missing)
   the report opens in the system browser, where the user prints or saves
   it as PDF. This is the "طباعة عصرية" path: the HTML itself is print
   styled, so browser print output is the final artifact.
3. **path**    — last resort: the file stays on disk and its path is
   surfaced so the user can open it by hand (never a silent failure).

The pure file-writing logic is separate from the page interactions so it
is unit-testable without a UI runtime.
"""

from __future__ import annotations

import datetime
import webbrowser
from pathlib import Path
from typing import Any

import flet as ft

from hf_offline.core.paths import ensure_dirs, reports_dir
from hf_offline.services.report_service import ReportService
from hf_offline.services.settings_repository import SettingsRepository


class ShareService:
    def __init__(self, reports: ReportService, settings: SettingsRepository):
        self.reports = reports
        self.settings = settings

    # ---- pure (testable) -------------------------------------------------

    def save_report(self, diagnosis_id: int) -> Path:
        """Render + persist the report HTML under the data dir's reports/.

        Returns the absolute path of the written file.
        """
        ensure_dirs()
        accent = self.settings.get("accent", "default") or "default"
        settings = self.settings.all()
        html = self.reports.report_html(diagnosis_id, accent=accent, settings=settings)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = reports_dir() / f"report_{diagnosis_id}_{ts}.html"
        path.write_text(html, encoding="utf-8")
        return path

    # ---- page interactions ------------------------------------------------

    def open_in_browser(self, path: Path) -> str:
        """Channel 2: open the report in the system browser (print/PDF)."""
        webbrowser.open(f"file://{path}")
        return "browser"

    def _try_native_share(self, page: ft.Page, path: Path) -> bool:
        """Channel 1: native share sheet, only when the bridge is present."""
        try:
            from flet_native_files import NativeFiles  # type: ignore
        except Exception:
            return False
        try:
            native = NativeFiles()
            page.overlay.append(native)
            page.update()
            import asyncio

            native.share_file(str(path))
            return True
        except Exception:
            return False

    def share_report(self, page: ft.Page, diagnosis_id: int) -> tuple[Path, str]:
        """Save + deliver a report. Returns ``(path, channel_used)``."""
        path = self.save_report(diagnosis_id)
        if self._try_native_share(page, path):
            return path, "native"
        if webbrowser.open(f"file://{path}"):
            return path, "browser"
        return path, "path"

    def print_report(self, page: ft.Page, diagnosis_id: int) -> tuple[Path, str]:
        """The "طباعة" action: same artifact as share, framed for printing
        (browser print dialog on desktop)."""
        path = self.save_report(diagnosis_id)
        if webbrowser.open(f"file://{path}"):
            return path, "browser"
        return path, "path"

    def last_report_path(self, diagnosis_id: int) -> Path | None:
        """The most recently saved file for a diagnosis (if any)."""
        ensure_dirs()
        files = sorted(reports_dir().glob(f"report_{diagnosis_id}_*.html"))
        return files[-1] if files else None


__all__ = ["ShareService"]
