# Phase 48 — Android Flet FloatingActionButton runtime fix

## Problem

Android/Flet failed when opening a screen that creates a `FloatingActionButton`:

```text
FloatingActionButton.__init__() got an unexpected keyword argument 'margin'
```

The project pins `flet==0.28.3`.  In this runtime, `margin` is not a supported
constructor argument for `ft.FloatingActionButton`; it is a layout/container
property.

## Fix

A compatibility factory was added:

```python
views.flet_compat.make_floating_action_button(...)
```

It filters unsupported constructor kwargs centrally and currently drops `margin`
for FABs.  Direct `ft.FloatingActionButton(...)` calls in Android views were
replaced in:

- `views/accounts_mobile_view.py`
- `views/users_mobile_view.py`

## Guard

Added:

```text
tools/flet_fab_compat_smoke_test.py
```

This prevents future direct FAB construction outside `flet_compat.py`.
