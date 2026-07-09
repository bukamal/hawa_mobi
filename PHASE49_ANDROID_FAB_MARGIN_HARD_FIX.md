# Phase 49 — Android Flet FAB margin hard fix

## Problem

Android still showed:

```text
FloatingActionButton.__init__() got an unexpected keyword argument 'margin'
```

## Root cause

`flet==0.28.3` rejects the `margin` keyword in `ft.FloatingActionButton`.
Phase 48 added a compatibility wrapper, but the call sites still passed
`margin=...` into the helper.  To make the fix deterministic in the packaged APK,
the margin argument was removed at the view level and the wrapper now also pops it
explicitly as a runtime backstop.

## Changed files

- `views/accounts_mobile_view.py`
- `views/users_mobile_view.py`
- `views/flet_compat.py`
- `tools/flet_fab_compat_smoke_test.py`
- `pyproject.toml` version bumped to `1.0.2`

## Verification

```text
python -m compileall -q .
python tools/flet_fab_compat_smoke_test.py
```

The guard now fails if:

- any Android view directly calls `ft.FloatingActionButton(...)`, or
- any Android view passes `margin=` to `make_floating_action_button(...)`.
