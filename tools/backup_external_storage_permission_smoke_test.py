# -*- coding: utf-8 -*-
"""Guard backup import against broad Android storage permissions."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
settings = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
export = (ROOT / "services" / "file_export_service.py").read_text(encoding="utf-8")

assert 'permissions = ["camera"]' in pyproject, (
    "Only camera should be requested through Flet"
)
for permission in (
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.MANAGE_EXTERNAL_STORAGE",
    "android.permission.READ_MEDIA_IMAGES",
    "android.permission.READ_MEDIA_VIDEO",
    "android.permission.READ_MEDIA_AUDIO",
):
    assert permission not in pyproject, f"Unnecessary permission remains: {permission}"
assert "StoragePermissionService.request" not in settings, (
    "Restore flow must not request broad storage access"
)
assert not (ROOT / "services" / "storage_permission_service.py").exists(), (
    "Obsolete broad-storage service must be removed"
)
assert "self._restore_file_picker" in settings, (
    "FilePicker must be retained on the view to keep callback alive"
)
assert "resolve_picker_file_path" in export, (
    "FilePicker content/path resolution missing"
)
assert "_write_picker_bytes_to_cache" in export, "Picker byte staging fallback missing"
assert "log_restore_event" in export and "backup_restore.log" in export, (
    "Restore diagnostic log missing"
)
assert "_is_file_picker_control" in compat and "legacy_filepicker" in compat, (
    "FilePicker attach guard missing"
)
print("✅ backup_external_storage_permission_smoke_test passed")
