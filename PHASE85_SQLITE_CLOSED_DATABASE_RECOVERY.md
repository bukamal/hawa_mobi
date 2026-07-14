# Phase 85 — SQLite Closed Database Recovery

## Problem
On Android/Flet, some UI callbacks can retain a thread-local SQLite connection after a different workflow closes the shared connection pool. When a screen such as **حسابات هوى الشام** or **التقارير** reuses that stale handle, the app shows:

```text
Cannot operate on a closed database.
```

## Fix
`DatabaseConnection.get_connection()` now validates cached thread-local and registry connections with a lightweight `SELECT 1` before returning them. If the handle is closed, it is discarded and a fresh SQLite connection is opened automatically.

This is a global fix for accounts, reports, company details, backup/restore refreshes, and any repository that uses `DatabaseConnection`.

## Regression test
Added:

```bash
PYTHONPATH=. python tools/sqlite_closed_connection_recovery_smoke_test.py
```

The test closes the active SQLite connection manually, then verifies that an existing `ReportingCenterService` and existing repositories recover without raising `Cannot operate on a closed database`.
