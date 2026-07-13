# Phase 73 — Android AlertDialog Blank White Surface Fix

Problem: closing any modal in the Android APK could leave a blank white surface above the main UI; it disappeared only after pressing Android Back.

Fix:
- AlertDialog is no longer appended to `page.overlay`.
- AlertDialog now uses the legacy `page.dialog = dlg` + `dlg.open = True` path only.
- `close_control()` no longer calls `page.close(control)`.
- `close_all_dialogs()` clears `page.dialog` and all app-managed transient controls.
- Added `tools/flet_alertdialog_no_overlay_blank_screen_smoke_test.py`.

Validation:
- compileall passed.
- dialog/snackbar/Flet compatibility smoke tests passed.
- quality_gate progressed through the earlier currency/API/report checks; in this sandbox the full gate timed out while running subprocess wrappers, but the remaining smoke tests passed individually.
