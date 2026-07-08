# Phase 39 — Android Service Control Guard

## Problem observed
On Android, pressing **Import backup** or **Scan camera** could trigger a full red Flet runtime panel:

```text
Unknown control: FilePicker
```

The previous compatibility layer avoided `FilePicker(on_result=...)`, but still attached `FilePicker` to `page.overlay`. Some Flet 0.8x Android/Web runtimes expose `ft.FilePicker` in Python while the Flutter client rejects it as an overlay control, producing the fatal red panel.

## Fix
- `views/flet_compat.py`
  - Added platform detection helpers.
  - `attach_service_control()` now prefers `page.services` / `_services` for service controls.
  - It no longer forces service controls into `page.overlay` on mobile when a service registry is unavailable.
  - Added `service_control_attached()` and `filepicker_unavailable_message()`.

- `views/settings_mobile_view.py`
  - Backup restore and company logo picker now check whether the FilePicker service was attached before calling `pick_files()`.
  - If the runtime does not support FilePicker, the app shows a normal snackbar instead of causing the red Flet overlay.

- `services/camera_permission_service.py`
  - PermissionHandler is attached via the same compatibility helper.
  - Removed direct `page.overlay.append(handler)` usage.

- `tools/filepicker_permission_compat_smoke_test.py`
  - Added static guards to prevent direct overlay attachment for permission services and to ensure the mobile Unknown FilePicker failure remains guarded.

## Important limitation
This phase prevents the fatal red screen and supports runtimes where `page.services` works. If the installed Flet Android runtime does not support FilePicker at all, native file selection will still be unavailable. In that case, backup import/logo selection must use a future native extension or a documented fallback workflow.

## Validation

```bash
python3 -m compileall -q .
PYTHONPATH=. python3 tools/filepicker_permission_compat_smoke_test.py
PYTHONPATH=. python3 tools/quality_gate.py
```

Result:

```text
filepicker_permission_compat_smoke_test passed
quality_gate passed
```
