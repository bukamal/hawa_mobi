# Phase 68 — Service Case Create Button Hard Fix

Fixed the Android service-case dialog where tapping **إنشاء ملف الخدمة** could appear to do nothing and leave the dialog open.

Changes:

- The service-case save callback now validates input immediately and shows inline errors inside the dialog.
- SQLite/REST service-case creation now runs off the Flet event callback with `run_async_task` + `asyncio.to_thread`.
- The button enters a visible busy state while the operation runs and is restored on failure.
- Failure details are shown inside the dialog and in a snackbar instead of failing silently behind an Android dialog surface.
- Arabic/Persian digits and Arabic decimal separators are supported in service-case amounts.

Added smoke test:

- `tools/service_case_dialog_save_callback_smoke_test.py`

Verified:

- `compileall`
- `service_case_dialog_save_callback_smoke_test.py`
- `service_case_workflow_smoke_test.py`
- `ledger_operation_core_smoke_test.py`
