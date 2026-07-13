# -*- coding: utf-8 -*-
"""Guard Phase 61 direct Android backup restore path.

When FilePicker returns a readable cache path on Android, the app must not stop
at an extra confirmation dialog.  Diagnostics from a real device showed:
`direct readable picker path: /data/user/0/.../cache/file_picker/...zip` and no
restore afterwards.  The selected file should now go directly to the restore
worker with a safety backup.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
settings = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
export = (ROOT / "services" / "file_export_service.py").read_text(encoding="utf-8")

assert "def _restore_selected_backup_path" in settings
assert 'self._restore_selected_backup_path(path, origin="filepicker")' in settings
assert (
    'FileExportService.log_restore_event(f"resolved picker backup path: {path}")'
    in settings
)
assert "restore async start origin=" in settings
assert "restore_backup_archive" in settings
assert "direct restore requested from" in settings
assert "read_restore_log_tail" in export
assert "inspect backup start" in export
assert "inspect zip members" in export

# The FilePicker branch should no longer build a confirmation AlertDialog after
# `resolved picker backup path`; that dialog was the point where the Android
# flow disappeared for the user.
marker = 'FileExportService.log_restore_event(f"resolved picker backup path: {path}")'
tail = settings[
    settings.index(marker) : settings.index(
        "def _confirm_restore_backup", settings.index(marker)
    )
]
assert "AlertDialog(" not in tail
assert "تأكيد استيراد النسخة الاحتياطية" not in tail

print("backup_restore_direct_picker_import_smoke_test passed")
