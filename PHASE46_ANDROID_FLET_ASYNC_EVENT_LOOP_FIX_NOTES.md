# Phase 46 — Android Flet async event-loop runtime fix

## Problem

The Android APK could crash at startup with:

```text
no running event loop
```

The crash was caused by raw `asyncio.create_task(...)` calls inside synchronous Flet view constructors and event handlers. On the pinned Android runtime (`flet==0.28.3`), those paths can run before a public asyncio loop is available.

## Fix

A centralized scheduler was added to `views/flet_compat.py`:

```python
run_async_task(page, async_callable, *args, **kwargs)
```

It schedules work through `page.run_task(...)` first, then falls back to an existing running loop, then to a daemon thread. This prevents Android startup from depending on `asyncio.create_task(...)`.

Updated call sites:

- `main.py`
- `views/splash_view.py`
- `views/activation_view.py`
- `views/settings_mobile_view.py`
- `views/dialogs/qr_pairing_dialog.py`
- `reports/share.py`

## Guard

Added:

```text
tools/flet_async_task_compat_smoke_test.py
```

and registered it in:

```text
tools/quality_gate.py
```

This prevents raw `asyncio.create_task(...)` from returning in Android UI/runtime code.

## Validation

Relevant Android guards passed:

```text
flet_async_task_compat_smoke_test passed
flet_alignment_compat_smoke_test passed
flet_entrypoint_compat_smoke_test passed
flet_build_command_smoke_test passed
```

Windows project tests also passed:

```text
63 passed
```
