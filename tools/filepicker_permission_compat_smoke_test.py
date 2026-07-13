# -*- coding: utf-8 -*-
"""Static guard for FilePicker and Android camera permission compatibility."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    settings = (ROOT / "views" / "settings_mobile_view.py").read_text(encoding="utf-8")
    compat = (ROOT / "views" / "flet_compat.py").read_text(encoding="utf-8")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    qr_dialog = (ROOT / "views" / "dialogs" / "qr_pairing_dialog.py").read_text(
        encoding="utf-8"
    )
    camera_service = (ROOT / "services" / "camera_permission_service.py").read_text(
        encoding="utf-8"
    )

    assert "FilePicker(on_result" not in settings, (
        "settings must not call FilePicker(on_result=...)"
    )
    assert "make_file_picker" in compat and "attach_service_control" in compat, (
        "compat helpers missing"
    )
    assert "make_file_picker(self._on_restore_backup_picked)" in settings, (
        "restore picker must use compat helper"
    )
    assert "make_file_picker(self._on_logo_picked)" in settings, (
        "logo picker must use compat helper"
    )
    assert "[tool.flet.android.permission]" in pyproject, (
        "modern Android permission table missing"
    )
    assert '"android.permission.CAMERA" = true' in pyproject, (
        "CAMERA permission not declared in modern table"
    )
    assert 'permissions = ["camera"]' in pyproject, (
        "Only camera should be requested; FilePicker uses SAF"
    )
    assert "CameraPermissionService.request" in qr_dialog, (
        "QR scanner must request/check camera permission"
    )
    assert (
        "PermissionHandler" in camera_service and "request_permission" in camera_service
    ), "permission handler bridge missing"
    assert "page.overlay" not in camera_service and "overlay" not in camera_service, (
        "camera permission service must not append service controls to overlay directly"
    )
    assert "page.services" in compat or '"services"' in compat, (
        "service controls should prefer page.services"
    )
    assert "_is_mobile_page" in compat and "Unknown control: FilePicker" in compat, (
        "compat must avoid mobile overlay Unknown FilePicker failures"
    )
    assert "service_control_attached" in settings, (
        "settings must not call FilePicker if service was not attached"
    )
    print("✅ filepicker_permission_compat_smoke_test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
