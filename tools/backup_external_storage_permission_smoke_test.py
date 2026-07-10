# -*- coding: utf-8 -*-
"""Static guard for Android external backup import hard fallback."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
settings = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
export = (ROOT / "services" / "file_export_service.py").read_text(encoding="utf-8")
storage = (ROOT / "services" / "storage_permission_service.py").read_text(encoding="utf-8")

assert 'permissions = ["camera", "storage"]' in pyproject, "Flet storage permission bundle missing"
assert 'android.permission.READ_EXTERNAL_STORAGE' in pyproject, "READ_EXTERNAL_STORAGE missing"
assert 'android.permission.WRITE_EXTERNAL_STORAGE' in pyproject, "WRITE_EXTERNAL_STORAGE missing"
assert 'android.permission.MANAGE_EXTERNAL_STORAGE' in pyproject, "MANAGE_EXTERNAL_STORAGE declaration missing for sideload fallback"
assert 'StoragePermissionService.request' in settings, "Settings must request storage permission before external import fallback"
assert 'self._restore_file_picker' in settings, "FilePicker must be retained on the view to keep callback alive"
assert 'find_external_backup_archives' in export, "External Download/Hawaa fallback scanner missing"
assert 'Download/Hawaa' in settings, "User-facing Download/Hawaa fallback missing"
assert 'log_restore_event' in export and 'backup_restore.log' in export, "Restore diagnostic log missing"
assert '_is_file_picker_control' in compat and 'legacy_filepicker' in compat, "FilePicker overlay-first attach guard missing"
assert 'request_permission' in storage and 'MANAGE_EXTERNAL_STORAGE' in storage, "Storage permission request bridge incomplete"
print('✅ backup_external_storage_permission_smoke_test passed')
