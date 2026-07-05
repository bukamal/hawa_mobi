# Phase 37 — Android FilePicker + Camera Permission Compatibility

## Fixed

- Import backup failed with `FilePicker.__init__() got an unexpected keyword argument 'on_result'` on the built APK runtime.
- Company logo selection used the same incompatible FilePicker constructor path.
- Camera QR action did not reliably request camera permission and pyproject only used an older `android_permissions` array.

## Changes

- Added `make_file_picker()` and `attach_service_control()` in `views/flet_compat.py`.
- Replaced `ft.FilePicker(on_result=...)` in settings restore/logo flows.
- Added modern Flet camera permission declarations:
  - `permissions = ["camera"]`
  - `[tool.flet.android.permission] "android.permission.CAMERA" = true`
- Added optional `CameraPermissionService` using Flet `PermissionHandler` when available.
- QR camera button now explains the difference between missing runtime permission and missing QR scanner control.

## Important

Camera permission alone does not create a QR scanner. The runtime must also provide a QR/Barcode scanner control or extension. Paste fallback remains mandatory until the APK is built with a real scanner plugin/control.
