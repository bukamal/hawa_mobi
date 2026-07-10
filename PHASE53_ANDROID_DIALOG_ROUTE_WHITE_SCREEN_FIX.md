# Phase 53 — Android Dialog Route / White Screen Fix

## Problem
On Android, after login and after saving a journal entry, a blank white modal
surface could remain above the main interface. It disappeared only when the user
pressed Android Back.

## Root cause
The app opens dialogs through Flet's native dialog route stack when available
(`page.show_dialog`). On some Flet Android builds the native route is pushed, but
`control.open` is not reliably set to `True`. The old `close_control()` only
called `page.pop_dialog()` when `control.open` was true. Therefore the app closed
or rebuilt the Python control while the native Android modal route remained.

## Fix
- `open_control()` now marks dialog-like controls as open after `page.show_dialog()`.
- `close_control()` now trusts the app-managed dialog stack and pops the exact
top dialog even when `control.open` is stale.
- Added `clear_transient_ui()` to close dialogs, drawers, snackbars and bottom
sheets before rebuilding the login/main shell or switching main tabs.
- `main.py` clears transient UI before splash, activation, login and main-shell
rebuild.
- `AppLayout.switch_page()` clears stale transient UI before rendering a new tab.
- Added `tools/flet_dialog_route_cleanup_smoke_test.py` and wired it into the
quality gate.

## Expected result
After login and after saving/editing a record, the main interface stays visible
without a stuck blank white overlay. The Android Back button should no longer be
needed to remove a stale modal page.
