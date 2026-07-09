# Phase 47 — Android Flet SQLite Thread Runtime Fix

## Problem
Android/Flet startup could fail with:

```text
SQLite objects created in a thread can only be used in that same thread
```

This happened because `DatabaseConnection` was a process singleton and reused one SQLite connection across Flet startup/task/event threads.

## Fix
`database/connection.py` now keeps SQLite connections per Python thread through a thread-local registry. `get_connection()` returns the current thread's own handle, while `close()` closes all cached handles before migrations/restore operations.

## Regression guard
Added:

```text
tools/sqlite_thread_safety_smoke_test.py
```

and included it in:

```text
tools/quality_gate.py
```

The quality gate also force-exits after successful completion because some Flet/mobile smoke tests can leave helper runtime threads alive in Linux shells after all checks pass.

## Validation

```text
Android quality_gate: passed
Windows pytest: 63 passed
```
