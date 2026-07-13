# -*- coding: utf-8 -*-
"""Guard Android restore buttons from becoming inert.

The restore buttons must not request Android storage permission or walk public
storage synchronously inside the Flet on_click handler.  Both behaviours made the
APK look unresponsive on real Android devices.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")

assert "async def _restore_from_public_downloads_async" in src, (
    "Download/Hawaa scan must run in an async/background task"
)
assert "run_async_task(self._page, self._restore_from_public_downloads_async" in src, (
    "Download/Hawaa button must schedule, not block"
)
assert "async def _confirm_restore_backup_async" in src, (
    "Backup restore must run in a background task"
)
assert "run_async_task(self._page, self._confirm_restore_backup_async" in src, (
    "Restore confirmation must schedule async restore"
)
assert "_restore_picker_watchdog" in src, "FilePicker must have a no-callback watchdog"
assert "restore_diag_btn" in src and "_show_restore_diagnostics" in src, (
    "Settings must expose restore diagnostics"
)

pick_body = src.split("def _pick_backup_to_restore", 1)[1].split(
    "def _restore_from_public_downloads", 1
)[0]
assert "StoragePermissionService.request" not in pick_body, (
    "Do not request storage permission inside FilePicker click handler"
)
public_click_body = src.split("def _restore_from_public_downloads", 1)[1].split(
    "async def _restore_from_public_downloads_async", 1
)[0]
assert "StoragePermissionService.request" not in public_click_body, (
    "Do not request storage permission inside Download/Hawaa click handler"
)
assert "find_external_backup_archives" not in public_click_body, (
    "Do not scan external storage synchronously in click handler"
)
print("backup_restore_button_nonblocking_smoke_test passed")
